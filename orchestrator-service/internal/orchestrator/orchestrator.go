package orchestrator

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"chip-orchestra/orchestrator-service/internal/dispatcher"
	edaclient "chip-orchestra/orchestrator-service/internal/eda"
	"chip-orchestra/orchestrator-service/internal/models"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

const defaultWorkspaceRoot = "/tmp/chip-orchestra/workspaces"

type StageDefinition struct {
	Name      string
	DependsOn []string
	Kind      string
	Gated     bool
}

type Service struct {
	db            *gorm.DB
	redis         *redis.Client
	agent         *dispatcher.Client
	eda           *edaclient.Client
	stageDefs     []StageDefinition
	workspaceRoot string
	inFlight      sync.Map
}

func workspaceRootFromEnv() string {
	if v := strings.TrimSpace(os.Getenv("WORKSPACE_ROOT")); v != "" {
		return v
	}
	return defaultWorkspaceRoot
}

func NewService(db *gorm.DB, redisClient *redis.Client, agent *dispatcher.Client, eda *edaclient.Client) *Service {
	return &Service{
		db:            db,
		redis:         redisClient,
		agent:         agent,
		eda:           eda,
		workspaceRoot: workspaceRootFromEnv(),
		stageDefs: []StageDefinition{
			{Name: "SPEC_INGEST", Kind: "agent"},
			{Name: "PLAN", DependsOn: []string{"SPEC_INGEST"}, Kind: "agent"},
			{Name: "RTL_GEN", DependsOn: []string{"PLAN"}, Kind: "agent"},
			// TB_GEN waits for RTL_GEN so the testbench is written against the
			// actual generated module interface instead of only the plan;
			// independently generated RTL+TB tend to drift and fail SIM.
			{Name: "TB_GEN", DependsOn: []string{"RTL_GEN"}, Kind: "agent"},
			{Name: "SIM", DependsOn: []string{"RTL_GEN", "TB_GEN"}, Kind: "eda"},
			// LINT runs only AFTER the simulation passes — a design that doesn't
			// even simulate correctly has no business being style-checked yet
			// (GarudaChip order: generate → tb → simulate → lint → harden).
			{Name: "LINT", DependsOn: []string{"SIM"}, Kind: "eda"},
			{Name: "RTL_REPAIR", DependsOn: []string{"SIM", "LINT"}, Kind: "agent"},
			{Name: "SYNTH", DependsOn: []string{"RTL_REPAIR"}, Kind: "eda", Gated: true},
			{Name: "PNR", DependsOn: []string{"SYNTH"}, Kind: "eda"},
			{Name: "STA", DependsOn: []string{"PNR"}, Kind: "eda"},
			{Name: "GL_SIM", DependsOn: []string{"PNR"}, Kind: "eda"},
			{Name: "RENDER", DependsOn: []string{"PNR"}, Kind: "eda"},
			{Name: "DRC_LVS", DependsOn: []string{"PNR"}, Kind: "eda"},
			// PADRING assembles the chip-level GF180 I/O pad ring around the
			// hardened core. It is a signoff-phase deliverable: it depends on
			// PNR (needs a hardened core to wrap) and runs in parallel with the
			// other post-PNR checks, then feeds SIGNOFF so the pad-ring
			// GDS/LEF/SVG is part of the tape-out evidence and approval gate.
			// A no-op (skipped) success when padring != gf180-v1.
			{Name: "PADRING", DependsOn: []string{"PNR"}, Kind: "eda"},
			{Name: "SIGNOFF", DependsOn: []string{"DRC_LVS", "STA", "GL_SIM", "RENDER", "PADRING"}, Kind: "agent", Gated: true},
			{Name: "EXPORT", DependsOn: []string{"SIGNOFF"}, Kind: "agent"},
		},
	}
}

func (s *Service) Definitions() []StageDefinition {
	return s.stageDefs
}

func (s *Service) QueueInitialStages(ctx context.Context, taskID string) error {
	var stage models.Stage
	if err := s.db.WithContext(ctx).Where("task_id = ? AND name = ?", taskID, "SPEC_INGEST").First(&stage).Error; err != nil {
		return err
	}
	stage.Status = models.StageStatusQueued
	if err := s.db.WithContext(ctx).Save(&stage).Error; err != nil {
		return err
	}
	return s.publishEvent(ctx, taskID, map[string]any{
		"type":      "stage.updated",
		"task_id":   taskID,
		"stage":     stage.Name,
		"status":    stage.Status,
		"progress":  0,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *Service) ScheduleLoop(ctx context.Context, tick time.Duration) {
	ticker := time.NewTicker(tick)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			_ = s.RunOnce(ctx)
		}
	}
}

func (s *Service) RunOnce(ctx context.Context) error {
	var tasks []models.Task
	if err := s.db.WithContext(ctx).Where("status IN ?", []models.TaskStatus{models.TaskStatusPending, models.TaskStatusRunning, models.TaskStatusBlocked}).Find(&tasks).Error; err != nil {
		return err
	}
	for _, task := range tasks {
		if err := s.evaluateTask(ctx, task.ID); err != nil {
			_ = s.publishEvent(ctx, task.ID, map[string]any{"type": "task.error", "task_id": task.ID, "error": err.Error(), "timestamp": time.Now().UTC().Format(time.RFC3339)})
		}
	}
	return nil
}

func (s *Service) evaluateTask(ctx context.Context, taskID string) error {
	var task models.Task
	if err := s.db.WithContext(ctx).First(&task, "id = ?", taskID).Error; err != nil {
		return err
	}
	var stages []models.Stage
	if err := s.db.WithContext(ctx).Where("task_id = ?", taskID).Find(&stages).Error; err != nil {
		return err
	}
	sort.Slice(stages, func(i, j int) bool { return stages[i].SortOrder < stages[j].SortOrder })

	stageMap := make(map[string]*models.Stage, len(stages))
	allDone := true
	failed := false
	blocked := false
	currentStage := ""

	for i := range stages {
		stage := &stages[i]
		stageMap[stage.Name] = stage
		switch stage.Status {
		case models.StageStatusRunning, models.StageStatusQueued, models.StageStatusDispatching, models.StageStatusRetryWait, models.StageStatusAwaitingApproval:
			allDone = false
			if currentStage == "" {
				currentStage = stage.Name
			}
		case models.StageStatusFailed:
			allDone = false
			failed = true
			if currentStage == "" {
				currentStage = stage.Name
			}
		case models.StageStatusBlocked:
			allDone = false
			blocked = true
			if currentStage == "" {
				currentStage = stage.Name
			}
		case models.StageStatusSucceeded, models.StageStatusReleased:
		default:
			allDone = false
			if currentStage == "" {
				currentStage = stage.Name
			}
		}
	}

	if task.Status == models.TaskStatusCancelled {
		return nil
	}

	for _, def := range s.stageDefs {
		stage := stageMap[def.Name]
		if stage == nil {
			continue
		}
		if stage.Status != models.StageStatusNotStarted && stage.Status != models.StageStatusRetryWait {
			continue
		}
		depsMet := true
		for _, dep := range def.DependsOn {
			depStage := stageMap[dep]
			if depStage == nil || (depStage.Status != models.StageStatusSucceeded && depStage.Status != models.StageStatusReleased) {
				depsMet = false
				break
			}
		}
		if depsMet {
			stage.Status = models.StageStatusQueued
			stage.Progress = 0
			if err := s.db.WithContext(ctx).Save(stage).Error; err != nil {
				return err
			}
			_ = s.publishEvent(ctx, taskID, map[string]any{"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": 0, "timestamp": time.Now().UTC().Format(time.RFC3339)})
			if currentStage == "" {
				currentStage = stage.Name
			}
		}
	}

	for i := range stages {
		stage := &stages[i]
		if stage.Status == models.StageStatusQueued {
			go s.dispatchStage(context.Background(), taskID, stage.ID)
		}
		if stage.Status == models.StageStatusRunning && stage.ExternalJobID != "" {
			go s.pollEDARun(context.Background(), taskID, stage.ID, stage.ExternalJobID)
		}
	}

	newStatus := models.TaskStatusRunning
	if blocked {
		newStatus = models.TaskStatusBlocked
	} else if failed {
		newStatus = models.TaskStatusFailed
	} else if allDone && len(stages) > 0 {
		newStatus = models.TaskStatusCompleted
	}
	if currentStage == "" && len(stages) > 0 {
		currentStage = stages[len(stages)-1].Name
	}

	updates := map[string]any{"status": newStatus, "current_stage": currentStage}
	if newStatus == models.TaskStatusCompleted {
		updates["eta_seconds"] = 0
	}
	return s.db.WithContext(ctx).Model(&models.Task{}).Where("id = ?", taskID).Updates(updates).Error
}

func (s *Service) dispatchStage(ctx context.Context, taskID, stageID string) {
	key := taskID + ":" + stageID
	if _, loaded := s.inFlight.LoadOrStore(key, true); loaded {
		return
	}
	defer s.inFlight.Delete(key)

	var task models.Task
	var stage models.Stage
	if err := s.db.WithContext(ctx).First(&task, "id = ?", taskID).Error; err != nil {
		return
	}
	if err := s.db.WithContext(ctx).First(&stage, "id = ?", stageID).Error; err != nil {
		return
	}
	if stage.Status != models.StageStatusQueued {
		return
	}

	now := time.Now().UTC()
	stage.Status = models.StageStatusDispatching
	stage.Progress = 10
	stage.StartedAt = &now
	stage.AttemptNumber++
	if err := s.db.WithContext(ctx).Save(&stage).Error; err != nil {
		return
	}

	attempt := models.StageAttempt{
		ID:        uuid.NewString(),
		TaskID:    taskID,
		StageID:   stage.ID,
		StageName: stage.Name,
		Attempt:   stage.AttemptNumber,
		Status:    models.StageStatusDispatching,
		StartedAt: &now,
	}

	def := s.definition(stage.Name)
	if def.Kind == "agent" {
		attempt.Service = "agent-service"
		prompt := fmt.Sprintf("Execute stage %s for task %s. Design brief: %s", stage.Name, task.Name, task.DesignBrief)
		attempt.Prompt = prompt
		_ = s.db.WithContext(ctx).Create(&attempt).Error

		stage.Status = models.StageStatusRunning
		stage.Progress = 35
		_ = s.db.WithContext(ctx).Save(&stage).Error
		_ = s.publishEvent(ctx, taskID, map[string]any{"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": stage.Progress, "timestamp": time.Now().UTC().Format(time.RFC3339)})

		req := s.buildInvokeRequest(taskID, task, stage.Name, prompt)
		resp, err := s.agent.Invoke(ctx, req)
		// TRANSIENT failures (agent-service restarting during a redeploy →
		// "EOF" / connection refused) must not burn the stage: wait for the
		// service to come back and re-dispatch instead of failing.
		for tries := 0; err != nil && isTransientErr(err) && tries < 3; tries++ {
			_ = s.publishEvent(ctx, taskID, map[string]any{
				"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": string(models.StageStatusRunning),
				"title":  fmt.Sprintf("%s connection lost — re-dispatching (%d/3)", stage.Name, tries+1),
				"detail": "The agent service connection dropped (likely a restart). Waiting for it to come back, then re-running this stage.",
				"tone":   "warning", "timestamp": time.Now().UTC().Format(time.RFC3339),
			})
			time.Sleep(20 * time.Second)
			resp, err = s.agent.Invoke(ctx, req)
		}
		if err != nil {
			s.failStage(ctx, &stage, &attempt, err.Error())
			return
		}
		// A stage only counts as done when the files it claims to have produced
		// actually exist in the shared workspace. Without this gate a stage (and
		// eventually the whole task) was marked Completed while its artifacts
		// showed up as Unavailable in the UI.
		if missing := s.missingArtifacts(taskID, resp.ArtifactRefs); len(missing) > 0 {
			s.failStage(ctx, &stage, &attempt, fmt.Sprintf(
				"stage reported success but %d declared artifact(s) are missing from the workspace: %s",
				len(missing), strings.Join(missing, ", ")))
			return
		}
		resultBytes, _ := json.Marshal(resp)
		attempt.Result = string(resultBytes)
		nowDone := time.Now().UTC()
		attempt.Status = models.StageStatusSucceeded
		attempt.CompletedAt = &nowDone
		stage.Status = models.StageStatusSucceeded
		stage.Progress = 100
		stage.CompletedAt = &nowDone
		_ = s.db.WithContext(ctx).Save(&attempt).Error
		_ = s.db.WithContext(ctx).Save(&stage).Error
		s.recordAgentOutputs(ctx, taskID, stage.Name, resp)
		_ = s.publishEvent(ctx, taskID, map[string]any{"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": 100, "timestamp": nowDone.Format(time.RFC3339)})
		_ = s.evaluateTask(ctx, taskID)
		return
	}

	attempt.Service = "eda-service"
	_ = s.db.WithContext(ctx).Create(&attempt).Error
	stage.Status = models.StageStatusRunning
	stage.Progress = 20
	_ = s.db.WithContext(ctx).Save(&stage).Error
	_ = s.publishEvent(ctx, taskID, map[string]any{"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": stage.Progress, "timestamp": time.Now().UTC().Format(time.RFC3339)})

	jobResp, err := s.eda.CreateJob(ctx, edaclient.CreateJobRequest{
		TaskID:        taskID,
		Stage:         stage.Name,
		Spec:          task.DesignBrief,
		WorkspaceRoot: s.taskWorkspace(taskID),
		ClockPort:     "clk",
		StageOptions: map[string]any{
			"pdk_id":         task.PDKID,
			"stdcell_lib_id": task.StdcellLibID,
			"padring":        task.Padring,
		},
	})
	if err != nil {
		s.failStage(ctx, &stage, &attempt, err.Error())
		return
	}
	stage.ExternalJobID = jobResp.JobID
	attempt.ExternalJobID = jobResp.JobID
	attempt.Status = models.StageStatusRunning
	_ = s.db.WithContext(ctx).Save(&attempt).Error
	_ = s.db.WithContext(ctx).Save(&stage).Error
	go s.pollEDARun(context.Background(), taskID, stage.ID, jobResp.JobID)
}

func (s *Service) pollEDARun(ctx context.Context, taskID, stageID, jobID string) {
	key := taskID + ":eda:" + stageID
	if _, loaded := s.inFlight.LoadOrStore(key, true); loaded {
		return
	}
	defer s.inFlight.Delete(key)

	for i := 0; i < 120; i++ {
		status, err := s.eda.GetJobStatus(ctx, jobID)
		if err != nil {
			time.Sleep(2 * time.Second)
			continue
		}

		var stage models.Stage
		var attempt models.StageAttempt
		if err := s.db.WithContext(ctx).First(&stage, "id = ?", stageID).Error; err != nil {
			return
		}
		if err := s.db.WithContext(ctx).Where("stage_id = ? AND external_job_id = ?", stageID, jobID).Order("created_at desc").First(&attempt).Error; err != nil {
			return
		}

		stage.Progress = status.Progress
		_ = s.db.WithContext(ctx).Save(&stage).Error
		_ = s.publishEvent(ctx, taskID, map[string]any{"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": status.Progress, "timestamp": time.Now().UTC().Format(time.RFC3339)})

		switch status.Status {
		case "COMPLETED":
			// HONESTY GATES — "the job ran" is not "the stage succeeded".
			// A SIM whose self-checking testbench FAILED triggers the
			// agent repair loop (bounded) instead of a green checkmark, and
			// hardening stages must actually produce a GDS.
			if stage.Name == "SIM" && simTestbenchFailed(status.Report) {
				// Auto-repair budget lives in Redis (2 rounds per manual retry) —
				// keying it on the cumulative RetryCount meant manual retries
				// exhausted the budget and the design never got repaired.
				repairKey := fmt.Sprintf("task:%s:sim_auto_repairs", taskID)
				rounds, _ := s.redis.Incr(ctx, repairKey).Result()
				if int(rounds) <= simRepairRounds() {
					s.repairAndRetrySim(ctx, taskID, &stage, &attempt, status.Report, int(rounds))
					return
				}
				s.failStage(ctx, &stage, &attempt, fmt.Sprintf(
					"self-checking testbench STILL FAILING after %d auto-repair rounds — see logs/sim.log and logs/rtl_repair_deep_agent.md; a manual Retry re-arms the loop (SIM_AUTO_REPAIR_ROUNDS to raise the budget)", simRepairRounds()))
				return
			}
			if stage.Name == "SIM" {
				_ = s.redis.Del(ctx, fmt.Sprintf("task:%s:sim_auto_repairs", taskID)).Err()
				// VERIFIABLE-OUTPUT gate: with chip-input data staged, a passing
				// testbench must also DUMP the chip's computed result AND the
				// Python golden model's desired output must exist for the
				// comparison — a green SIM without both is not a verified chip.
				if s.hasChipInput(taskID) && !s.hasChipOutput(taskID) {
					s.failStage(ctx, &stage, &attempt,
						"testbench passed but never dumped the chip's output (waves/chip_output.mem) — retry TB_GEN to regenerate the testbench with the output-dump contract")
					return
				}
				if s.hasChipInput(taskID) {
					if _, err := os.Stat(filepath.Join(s.taskWorkspace(taskID), "waves", "golden_output.mem")); err != nil {
						s.failStage(ctx, &stage, &attempt,
							"no golden_output.mem — the Python golden model's desired output is required to verify the chip; retry TB_GEN")
						return
					}
				}
			}
			if stage.Name == "PNR" || stage.Name == "DRC_LVS" {
				if !s.hasGDS(taskID) {
					// HARDEN auto-repair loop (mirror of SIM's): most no-GDS
					// failures are synthesizability defects in the RTL (e.g.
					// SystemVerilog-only ports yosys rejects) — let the repair
					// agent fix the RTL from the LibreLane log, then re-harden.
					repairKey := fmt.Sprintf("task:%s:harden_auto_repairs", taskID)
					rounds, _ := s.redis.Incr(ctx, repairKey).Result()
					if int(rounds) <= hardenRepairRounds() {
						s.repairAndRetryHarden(ctx, taskID, &stage, &attempt, int(rounds))
						return
					}
					s.failStage(ctx, &stage, &attempt, fmt.Sprintf(
						"%s still produces no GDS after %d auto-repair rounds — see logs/librelane.log; a manual Retry re-arms the loop (HARDEN_AUTO_REPAIR_ROUNDS to raise the budget)",
						stage.Name, hardenRepairRounds()))
					return
				}
				_ = s.redis.Del(ctx, fmt.Sprintf("task:%s:harden_auto_repairs", taskID)).Err()
				// FUNCTIONAL-CHIP gate: a layout that misses setup timing is
				// not a working chip. The EDA side already relaxes the clock
				// to close timing; if WNS is still negative here, stop honestly.
				if stage.Name == "PNR" {
					if wns, ok := s.pnrWNS(taskID); ok && wns < -0.001 {
						s.failStage(ctx, &stage, &attempt, fmt.Sprintf(
							"setup timing NOT met (WNS %.3f ns) even after automatic clock relaxation — the chip would not function at the reported clock; see logs/librelane.log", wns))
						return
					}
				}
			}
			now := time.Now().UTC()
			stage.Status = models.StageStatusSucceeded
			stage.Progress = 100
			stage.CompletedAt = &now
			attempt.Status = models.StageStatusSucceeded
			attempt.CompletedAt = &now
			payload, _ := json.Marshal(status.Report)
			attempt.Result = string(payload)
			_ = s.db.WithContext(ctx).Save(&attempt).Error
			_ = s.db.WithContext(ctx).Save(&stage).Error
			s.recordEDAOutputs(ctx, taskID, stage.Name, status.Report)
			_ = s.publishEvent(ctx, taskID, map[string]any{"type": "artifact.created", "task_id": taskID, "stage": stage.Name, "status": stage.Status, "progress": 100, "timestamp": now.Format(time.RFC3339)})
			_ = s.evaluateTask(ctx, taskID)
			return
		case "FAILED":
			s.failStage(ctx, &stage, &attempt, status.Error)
			return
		}

		time.Sleep(2 * time.Second)
	}
}

// ResetSimRepairBudget re-arms the SIM auto-repair loop. Called from the
// MANUAL retry API only — RetryStage itself is also invoked by the auto-repair
// loop, and resetting there erased the counter the loop had just incremented
// (the "auto-repair round 9" infinite loop).
func (s *Service) ResetSimRepairBudget(ctx context.Context, taskID string) {
	_ = s.redis.Del(ctx, fmt.Sprintf("task:%s:sim_auto_repairs", taskID)).Err()
	_ = s.redis.Del(ctx, fmt.Sprintf("task:%s:harden_auto_repairs", taskID)).Err()
}

func (s *Service) RetryStage(ctx context.Context, taskID, stageName string) error {
	var stages []models.Stage
	if err := s.db.WithContext(ctx).Where("task_id = ?", taskID).Find(&stages).Error; err != nil {
		return err
	}
	stageSet := map[string]*models.Stage{}
	for i := range stages {
		stageSet[stages[i].Name] = &stages[i]
	}
	for _, stage := range stages {
		if stage.Name == stageName || s.dependsTransitively(stage.Name, stageName) {
			updates := map[string]any{"status": models.StageStatusNotStarted, "progress": 0, "last_error": "", "external_job_id": ""}
			if stage.Name == stageName {
				updates["retry_count"] = stage.RetryCount + 1
			}
			if err := s.db.WithContext(ctx).Model(&models.Stage{}).Where("id = ?", stage.ID).Updates(updates).Error; err != nil {
				return err
			}
		}
	}
	return s.evaluateTask(ctx, taskID)
}

func (s *Service) ApproveStage(ctx context.Context, taskID, stageName string) error {
	var stage models.Stage
	if err := s.db.WithContext(ctx).Where("task_id = ? AND name = ?", taskID, strings.ToUpper(stageName)).First(&stage).Error; err != nil {
		return err
	}
	stage.Status = models.StageStatusReleased
	stage.Progress = 100
	if err := s.db.WithContext(ctx).Save(&stage).Error; err != nil {
		return err
	}
	return s.evaluateTask(ctx, taskID)
}

func (s *Service) taskWorkspace(taskID string) string {
	return filepath.Join(s.workspaceRoot, taskID)
}

// TaskWorkspace exposes the task's shared-workspace directory to the API layer
// (attachment uploads, disk-backed workspace file reads).
func (s *Service) TaskWorkspace(taskID string) string {
	return s.taskWorkspace(taskID)
}

// missingArtifacts returns the declared workspace-relative artifact paths that
// do NOT exist on disk. Used to gate agent-stage success so a stage can never
// be marked done while its outputs are unavailable. When the workspace
// directory itself is absent (e.g. volume not mounted in a dev setup) the
// check is skipped rather than failing every stage.
func (s *Service) missingArtifacts(taskID string, refs []string) []string {
	if len(refs) == 0 {
		return nil
	}
	workspace := s.taskWorkspace(taskID)
	if _, err := os.Stat(workspace); err != nil {
		return nil
	}
	missing := make([]string, 0)
	for _, ref := range refs {
		ref = strings.TrimSpace(ref)
		if ref == "" || strings.Contains(ref, "..") || filepath.IsAbs(ref) {
			continue
		}
		if _, err := os.Stat(filepath.Join(workspace, filepath.FromSlash(ref))); err != nil {
			missing = append(missing, ref)
		}
	}
	return missing
}

// edaReportPaths returns the relative report file names produced by the EDA
// stages, used to give downstream agent stages (SIGNOFF/EXPORT) evidence to
// consume from the shared workspace.
func (s *Service) edaReportPaths() []string {
	paths := make([]string, 0, len(s.stageDefs))
	for _, def := range s.stageDefs {
		if def.Kind == "eda" {
			paths = append(paths, fmt.Sprintf("reports/%s_report.json", strings.ToLower(def.Name)))
		}
	}
	return paths
}

// buildInvokeRequest assembles the agent invoke request for a stage, wiring the
// shared workspace root and (for signoff/export) the EDA report inventory.
func (s *Service) buildInvokeRequest(taskID string, task models.Task, stageName, prompt string) dispatcher.InvokeRequest {
	workspace := s.taskWorkspace(taskID)
	req := dispatcher.InvokeRequest{
		TaskID:        taskID,
		Stage:         stageName,
		Prompt:        prompt,
		Tools:         []string{"update_task_status", "track_task_progress", "get_user_context", "submit_eda_job", "get_eda_result", "read_artifact", "write_artifact"},
		WorkspaceRoot: workspace,
		Context: map[string]any{
			"task_name":      task.Name,
			"task_status":    task.Status,
			"current_stage":  task.CurrentStage,
			"pdk_id":         task.PDKID,
			"stdcell_lib_id": task.StdcellLibID,
			"llm_model":      task.LLMModel,
			"design_brief":   task.DesignBrief,
			"workspace_root": workspace,
		},
	}
	if stageName == "SIGNOFF" || stageName == "EXPORT" {
		req.EDAReports = s.edaReportPaths()
	}
	return req
}

func (s *Service) definition(name string) StageDefinition {
	for _, def := range s.stageDefs {
		if def.Name == name {
			return def
		}
	}
	return StageDefinition{Name: name, Kind: "agent"}
}

func (s *Service) dependsTransitively(stageName, upstream string) bool {
	defMap := map[string]StageDefinition{}
	for _, def := range s.stageDefs {
		defMap[def.Name] = def
	}
	visited := map[string]bool{}
	var visit func(string) bool
	visit = func(name string) bool {
		if visited[name] {
			return false
		}
		visited[name] = true
		def, ok := defMap[name]
		if !ok {
			return false
		}
		for _, dep := range def.DependsOn {
			if dep == upstream || visit(dep) {
				return true
			}
		}
		return false
	}
	return visit(stageName)
}

// simRepairRounds: how many automatic repair→re-sim rounds SIM gets before an
// honest stop. Behavioral convergence often needs several passes — the old
// hard cap of 2 stranded runs that were still making progress.
func simRepairRounds() int {
	if v := strings.TrimSpace(os.Getenv("SIM_AUTO_REPAIR_ROUNDS")); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 10
}

// isTransientErr matches connection-level failures worth re-dispatching
// (service restarting), as opposed to real stage errors.
func isTransientErr(err error) bool {
	msg := err.Error()
	for _, needle := range []string{"EOF", "connection refused", "connection reset", "no such host", "broken pipe"} {
		if strings.Contains(msg, needle) {
			return true
		}
	}
	return false
}

// simTestbenchFailed reads the SIM report's verdict: the self-checking
// testbench printed FAILED / $fatal / a mismatch (metrics.passed == false).
func simTestbenchFailed(report map[string]any) bool {
	metrics, _ := report["metrics"].(map[string]any)
	if metrics == nil {
		return false
	}
	passed, ok := metrics["passed"].(bool)
	return ok && !passed
}

// hasGDS reports whether hardening actually produced a layout stream.
func (s *Service) hasGDS(taskID string) bool {
	matches, _ := filepath.Glob(filepath.Join(s.taskWorkspace(taskID), "gds", "*.gds*"))
	return len(matches) > 0
}

// hasChipInput: a data stimulus was staged for the chip (inference flow).
func (s *Service) hasChipInput(taskID string) bool {
	ws := s.taskWorkspace(taskID)
	for _, rel := range []string{"context/chip_input_grid.json", "waves/chip_input.png"} {
		if _, err := os.Stat(filepath.Join(ws, filepath.FromSlash(rel))); err == nil {
			return true
		}
	}
	return false
}

// hasChipOutput: the testbench dumped what the RTL computed.
func (s *Service) hasChipOutput(taskID string) bool {
	matches, _ := filepath.Glob(filepath.Join(s.taskWorkspace(taskID), "waves", "*output*"))
	return len(matches) > 0
}

// repairAndRetrySim is the bounded self-heal loop (GarudaChip's corrector):
// the testbench failed → dispatch the RTL_REPAIR deep agent with the failure
// evidence, then reset SIM (and its dependents) so it re-runs on the fix.
func (s *Service) repairAndRetrySim(ctx context.Context, taskID string, stage *models.Stage, attempt *models.StageAttempt, report map[string]any, round int) {
	now := time.Now().UTC()
	attempt.Status = models.StageStatusFailed
	attempt.ErrorMessage = "self-checking testbench FAILED — dispatching auto-repair"
	attempt.CompletedAt = &now
	payload, _ := json.Marshal(report)
	attempt.Result = string(payload)
	_ = s.db.WithContext(ctx).Save(attempt).Error
	_ = s.publishEvent(ctx, taskID, map[string]any{
		"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": string(models.StageStatusRunning),
		"title":  fmt.Sprintf("SIM failed — auto-repair round %d/%d", round, simRepairRounds()),
		"detail": "The self-checking testbench FAILED. The RTLAuthor deep agent is debugging the design against a golden model (logs/rtl_repair_deep_agent.md), then SIM re-runs automatically.",
		"tone":   "warning", "timestamp": now.Format(time.RFC3339),
	})

	var task models.Task
	if err := s.db.WithContext(ctx).First(&task, "id = ?", taskID).Error; err == nil {
		prompt := fmt.Sprintf(
			"SIMULATION FAILURE for task %s: the self-checking testbench FAILED. Debug the chip's behaviour against a golden model and fix the faulty RTL (see logs/sim.log). Design brief: %s",
			task.Name, task.DesignBrief)
		if _, err := s.agent.Invoke(ctx, s.buildInvokeRequest(taskID, task, "RTL_REPAIR", prompt)); err != nil {
			s.failStage(ctx, stage, attempt, "auto-repair dispatch failed: "+err.Error())
			return
		}
	}
	// Reset SIM + dependents and re-queue; RetryStage bumps stage.RetryCount,
	// which bounds this loop.
	if err := s.RetryStage(ctx, taskID, stage.Name); err != nil {
		s.failStage(ctx, stage, attempt, "could not requeue SIM after repair: "+err.Error())
	}
}

// pnrWNS reads the setup WNS from reports/pnr_report.json metrics.
func (s *Service) pnrWNS(taskID string) (float64, bool) {
	data, err := os.ReadFile(filepath.Join(s.taskWorkspace(taskID), "reports", "pnr_report.json"))
	if err != nil {
		return 0, false
	}
	var parsed struct {
		Metrics map[string]any `json:"metrics"`
	}
	if json.Unmarshal(data, &parsed) != nil {
		return 0, false
	}
	if v, ok := parsed.Metrics["wns_ns"].(float64); ok {
		return v, true
	}
	return 0, false
}

func hardenRepairRounds() int {
	if v := strings.TrimSpace(os.Getenv("HARDEN_AUTO_REPAIR_ROUNDS")); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 3
}

// repairAndRetryHarden dispatches the repair agent on a hardening (no-GDS)
// failure with the LibreLane log, then re-queues the failed stage. Behavior
// must stay identical — the agent is told SIM already passes and must keep
// passing.
func (s *Service) repairAndRetryHarden(ctx context.Context, taskID string, stage *models.Stage, attempt *models.StageAttempt, round int) {
	now := time.Now().UTC()
	attempt.Status = models.StageStatusFailed
	attempt.ErrorMessage = "hardening produced no GDS — dispatching auto-repair"
	attempt.CompletedAt = &now
	_ = s.db.WithContext(ctx).Save(attempt).Error
	_ = s.publishEvent(ctx, taskID, map[string]any{
		"type": "stage.updated", "task_id": taskID, "stage": stage.Name, "status": string(models.StageStatusRunning),
		"title":  fmt.Sprintf("%s failed — hardening auto-repair round %d/%d", stage.Name, round, hardenRepairRounds()),
		"detail": "LibreLane produced no GDS. The RTLAuthor deep agent is fixing the synthesizability defect from logs/librelane.log (behavior must stay identical — SIM must still pass), then hardening re-runs automatically.",
		"tone":   "warning", "timestamp": now.Format(time.RFC3339),
	})

	logTail := ""
	if data, err := os.ReadFile(filepath.Join(s.taskWorkspace(taskID), "logs", "librelane.log")); err == nil {
		text := string(data)
		if len(text) > 4000 {
			text = text[len(text)-4000:]
		}
		logTail = text
	}
	var task models.Task
	if err := s.db.WithContext(ctx).First(&task, "id = ?", taskID).Error; err == nil {
		prompt := fmt.Sprintf(
			"HARDENING FAILURE for task %s: LibreLane produced no GDS at stage %s. The simulation ALREADY PASSES "+
				"(chip output matches the desired output) — do NOT change behavior; fix ONLY the synthesizability "+
				"defect the log shows (common: SystemVerilog-only constructs like unpacked array PORTS that yosys' "+
				"Verilog-2005 frontend rejects — flatten them to packed vectors and update every instantiation). "+
				"After the fix, re-run iverilog+vvp yourself and confirm the testbench still reports TEST PASSED "+
				"and the chip output still matches waves/golden_output.mem. LibreLane log tail:\n%s\nDesign brief: %s",
			task.Name, stage.Name, logTail, task.DesignBrief)
		if _, err := s.agent.Invoke(ctx, s.buildInvokeRequest(taskID, task, "RTL_REPAIR", prompt)); err != nil {
			s.failStage(ctx, stage, attempt, "hardening auto-repair dispatch failed: "+err.Error())
			return
		}
	}
	if err := s.RetryStage(ctx, taskID, stage.Name); err != nil {
		s.failStage(ctx, stage, attempt, "could not requeue "+stage.Name+" after repair: "+err.Error())
	}
}

func (s *Service) failStage(ctx context.Context, stage *models.Stage, attempt *models.StageAttempt, msg string) {
	now := time.Now().UTC()
	stage.Status = models.StageStatusFailed
	stage.LastError = msg
	stage.Progress = 100
	stage.CompletedAt = &now
	attempt.Status = models.StageStatusFailed
	attempt.ErrorMessage = msg
	attempt.CompletedAt = &now
	_ = s.db.WithContext(ctx).Save(attempt).Error
	_ = s.db.WithContext(ctx).Save(stage).Error
	_ = s.publishEvent(ctx, stage.TaskID, map[string]any{"type": "stage.updated", "task_id": stage.TaskID, "stage": stage.Name, "status": stage.Status, "error": msg, "progress": 100, "timestamp": now.Format(time.RFC3339)})
	_ = s.evaluateTask(ctx, stage.TaskID)
}

// stageImage finds the picture worth SHOWING in the execution log for a
// completed stage: the user's uploaded diagram after SPEC_INGEST, the GDS
// layout render after RENDER/SIGNOFF/EXPORT. Returns a workspace-relative
// path or "".
func (s *Service) stageImage(taskID, stageName string) string {
	imageRE := regexp.MustCompile(`(?i)\.(png|jpe?g|webp|bmp|gif|svg)$`)
	scan := func(dir string) string {
		entries, err := os.ReadDir(filepath.Join(s.taskWorkspace(taskID), dir))
		if err != nil {
			return ""
		}
		for _, entry := range entries {
			if !entry.IsDir() && imageRE.MatchString(entry.Name()) && !strings.HasPrefix(entry.Name(), ".") {
				return dir + "/" + entry.Name()
			}
		}
		return ""
	}
	switch stageName {
	case "SPEC_INGEST", "PLAN":
		return scan("context/uploads")
	case "SIM", "GL_SIM":
		return scan("waves")
	case "RENDER", "DRC_LVS", "SIGNOFF", "EXPORT":
		if img := scan("gds"); img != "" {
			return img
		}
		// RENDER writes its layout image to reports/gds.png
		for _, candidate := range []string{"reports/gds.png", "reports/schematic.png"} {
			if _, err := os.Stat(filepath.Join(s.taskWorkspace(taskID), filepath.FromSlash(candidate))); err == nil {
				return candidate
			}
		}
	case "PADRING":
		// The pad-ring SVG preview is the natural thumbnail for this stage.
		if img := scan("padring"); img != "" {
			return img
		}
		if img := scan("gds"); img != "" {
			return img
		}
	}
	return ""
}

func (s *Service) recordAgentOutputs(ctx context.Context, taskID, stageName string, resp *dispatcher.InvokeResponse) {
	event := map[string]any{"id": uuid.NewString(), "time": time.Now().Format("15:04"), "timestamp": time.Now().UTC().Format(time.RFC3339), "title": fmt.Sprintf("%s completed", stageName), "detail": resp.Summary, "tone": "success"}
	if img := s.stageImage(taskID, stageName); img != "" {
		event["image"] = img
	}
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:events", taskID), event)
	for _, item := range resp.Diagnostics {
		_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:diagnosis", taskID), item)
	}
	for _, artifact := range resp.Artifacts {
		_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:artifacts", taskID), artifact)
	}
	for path, content := range resp.WorkspaceFiles {
		_ = s.redis.Set(ctx, fmt.Sprintf("task:%s:workspace:file:%s", taskID, path), content, 0).Err()
		_ = s.redis.HSet(ctx, fmt.Sprintf("task:%s:workspace:index", taskID), path, fmt.Sprintf("generated by %s", stageName)).Err()
	}
}

func (s *Service) recordEDAOutputs(ctx context.Context, taskID, stageName string, report map[string]any) {
	reportName := strings.ToLower(stageName) + "_report.json"
	// Say WHAT happened, not just "a report exists": the stage's own summary
	// plus its headline metrics.
	detail, _ := report["summary"].(string)
	if detail == "" {
		detail = "EDA execution completed and produced a report."
	}
	if metrics, ok := report["metrics"].(map[string]any); ok && len(metrics) > 0 {
		keys := make([]string, 0, len(metrics))
		for k := range metrics {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		parts := make([]string, 0, 6)
		for _, k := range keys {
			if len(parts) >= 6 {
				break
			}
			parts = append(parts, fmt.Sprintf("%s=%v", k, metrics[k]))
		}
		detail += " [" + strings.Join(parts, " · ") + "]"
	}
	event := map[string]any{"id": uuid.NewString(), "time": time.Now().Format("15:04"), "timestamp": time.Now().UTC().Format(time.RFC3339), "title": fmt.Sprintf("%s report ready", stageName), "detail": detail, "tone": "success"}
	if img := s.stageImage(taskID, stageName); img != "" {
		event["image"] = img
	}
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:events", taskID), event)
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:artifacts", taskID), map[string]any{"id": uuid.NewString(), "name": reportName, "type": "REPORT", "owner": "EDA Service", "path": "reports/" + reportName})
	payload, _ := json.Marshal(report)
	_ = s.redis.Set(ctx, fmt.Sprintf("task:%s:artifact:%s", taskID, reportName), string(payload), 0).Err()
}

// stageActivity says WHAT is being done in a stage, so the execution log
// narrates the run instead of showing bare status flips.
var stageActivity = map[string]string{
	"SPEC_INGEST": "SpecInterpreter is decomposing the design brief and digesting attached images/PDFs (vision).",
	"PLAN":        "FlowAssistant deep agent is researching references online and writing the execution plan + build contract.",
	"RTL_GEN":     "RTLAuthor deep agent is generating the RTL modules (compile-checked on every write) — live transcript: logs/rtl_gen_deep_agent.md.",
	"RTL_REPAIR":  "RTLAuthor deep agent is repairing compile errors (web fix search + remembered lessons) — live transcript: logs/rtl_repair_deep_agent.md.",
	"TB_GEN":      "Verifier deep agent is writing self-checking testbenches — live transcript: logs/tb_gen_deep_agent.md.",
	"SIM":         "EDA service is compiling and simulating the design with the generated testbench (iverilog/vvp).",
	"LINT":        "EDA service is linting the RTL.",
	"SYNTH":       "EDA service is synthesizing the design (yosys via LibreLane).",
	"PNR":         "EDA service is running place & route.",
	"STA":         "EDA service is running static timing analysis.",
	"GL_SIM":      "EDA service is running gate-level simulation.",
	"RENDER":      "EDA service is rendering the GDS layout image.",
	"DRC_LVS":     "EDA service is running DRC/LVS checks.",
	"PADRING":     "EDA service is assembling the GF180 chip-level I/O pad ring (GDS/LEF/DEF/SVG deliverables).",
	"SIGNOFF":     "FlowAssistant is assembling the signoff summary from the EDA evidence.",
	"EXPORT":      "FlowAssistant is assembling the final report, runbook and PDF.",
}

// publishEvent enriches every event with the display fields the runbook needs
// (id/time/title/detail/tone) — bare status payloads rendered as EMPTY rows in
// the execution log.
func (s *Service) publishEvent(ctx context.Context, taskID string, payload map[string]any) error {
	if _, ok := payload["id"]; !ok {
		payload["id"] = uuid.NewString()
	}
	if _, ok := payload["time"]; !ok {
		payload["time"] = time.Now().Format("15:04")
	}
	// Full timestamp so the frontend can render the time in the USER'S
	// timezone — the bare "15:04" string is container-local (UTC) and showed
	// wrong wall-clock times.
	if _, ok := payload["timestamp"]; !ok {
		payload["timestamp"] = time.Now().UTC().Format(time.RFC3339)
	}
	stageName, _ := payload["stage"].(string)
	status, _ := payload["status"].(string)
	if _, ok := payload["title"]; !ok && stageName != "" {
		title := stageName
		switch models.StageStatus(status) {
		case models.StageStatusRunning, models.StageStatusDispatching:
			title = fmt.Sprintf("%s running", stageName)
			if progress, okP := payload["progress"].(int); okP && progress > 0 {
				title = fmt.Sprintf("%s running (%d%%)", stageName, progress)
			}
		case models.StageStatusSucceeded:
			title = fmt.Sprintf("%s completed", stageName)
		case models.StageStatusFailed:
			title = fmt.Sprintf("%s failed", stageName)
		default:
			title = fmt.Sprintf("%s %s", stageName, strings.ToLower(status))
		}
		payload["title"] = title
	}
	if _, ok := payload["detail"]; !ok {
		if msg, okE := payload["error"].(string); okE && msg != "" {
			payload["detail"] = msg
		} else if activity, okA := stageActivity[stageName]; okA {
			payload["detail"] = activity
		}
	}
	if _, ok := payload["tone"]; !ok {
		switch models.StageStatus(status) {
		case models.StageStatusFailed:
			payload["tone"] = "warning"
		case models.StageStatusSucceeded:
			payload["tone"] = "success"
		default:
			payload["tone"] = "info"
		}
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	if err := s.redis.Publish(ctx, fmt.Sprintf("task:%s:events:pubsub", taskID), encoded).Err(); err != nil {
		return err
	}
	return s.redis.RPush(ctx, fmt.Sprintf("task:%s:events", taskID), encoded).Err()
}

func (s *Service) pushListJSON(ctx context.Context, key string, value any) error {
	encoded, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return s.redis.RPush(ctx, key, encoded).Err()
}
