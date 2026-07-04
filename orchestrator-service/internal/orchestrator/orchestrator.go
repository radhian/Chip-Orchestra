package orchestrator

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
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
			{Name: "TB_GEN", DependsOn: []string{"PLAN"}, Kind: "agent"},
			{Name: "SIM", DependsOn: []string{"RTL_GEN", "TB_GEN"}, Kind: "eda"},
			{Name: "LINT", DependsOn: []string{"RTL_GEN"}, Kind: "eda"},
			{Name: "SYNTH", DependsOn: []string{"SIM", "LINT"}, Kind: "eda", Gated: true},
			{Name: "PNR", DependsOn: []string{"SYNTH"}, Kind: "eda"},
			{Name: "DRC_LVS", DependsOn: []string{"PNR"}, Kind: "eda"},
			{Name: "SIGNOFF", DependsOn: []string{"DRC_LVS"}, Kind: "agent", Gated: true},
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

		resp, err := s.agent.Invoke(ctx, s.buildInvokeRequest(taskID, task, stage.Name, prompt))
		if err != nil {
			s.failStage(ctx, &stage, &attempt, err.Error())
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

func (s *Service) recordAgentOutputs(ctx context.Context, taskID, stageName string, resp *dispatcher.InvokeResponse) {
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:events", taskID), map[string]any{"id": uuid.NewString(), "time": time.Now().Format("15:04"), "title": fmt.Sprintf("%s completed", stageName), "detail": resp.Summary, "tone": "success"})
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
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:events", taskID), map[string]any{"id": uuid.NewString(), "time": time.Now().Format("15:04"), "title": fmt.Sprintf("%s report ready", stageName), "detail": "Mock EDA execution completed and produced a report.", "tone": "success"})
	_ = s.pushListJSON(ctx, fmt.Sprintf("task:%s:artifacts", taskID), map[string]any{"id": uuid.NewString(), "name": reportName, "type": "REPORT", "owner": "EDA Service"})
	payload, _ := json.Marshal(report)
	_ = s.redis.Set(ctx, fmt.Sprintf("task:%s:artifact:%s", taskID, reportName), string(payload), 0).Err()
}

func (s *Service) publishEvent(ctx context.Context, taskID string, payload map[string]any) error {
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
