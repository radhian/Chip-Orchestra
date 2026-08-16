package orchestrator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"chip-orchestra/orchestrator-service/internal/dispatcher"
	"chip-orchestra/orchestrator-service/internal/models"

	miniredis "github.com/alicebob/miniredis/v2"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestQueueInitialStagesMarksSpecIngestQueued(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusPending, "SPEC_INGEST")
	h.seedStages(taskID,
		stageSeed{Name: "SPEC_INGEST", Status: models.StageStatusNotStarted},
	)

	require.NoError(t, h.service.QueueInitialStages(context.Background(), taskID))

	stage := h.mustStage(taskID, "SPEC_INGEST")
	assert.Equal(t, models.StageStatusQueued, stage.Status)

	events, err := h.redisClient.LRange(context.Background(), "task:"+taskID+":events", 0, -1).Result()
	require.NoError(t, err)
	require.Len(t, events, 1)
	assert.Contains(t, events[0], "SPEC_INGEST")
}

func TestEvaluateTaskQueuesAndDispatchesEligibleAgentStage(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusPending, "SPEC_INGEST")
	h.seedStages(taskID,
		stageSeed{Name: "SPEC_INGEST", Status: models.StageStatusSucceeded},
		stageSeed{Name: "PLAN", Status: models.StageStatusNotStarted},
	)

	require.NoError(t, h.service.evaluateTask(context.Background(), taskID))

	require.Eventually(t, func() bool {
		return h.mustStage(taskID, "PLAN").Status == models.StageStatusSucceeded
	}, 3*time.Second, 50*time.Millisecond)

	var attempts []models.StageAttempt
	require.NoError(t, h.db.Where("task_id = ?", taskID).Find(&attempts).Error)
	require.Len(t, attempts, 1)
	assert.Equal(t, "PLAN", attempts[0].StageName)
	assert.Equal(t, models.StageStatusSucceeded, attempts[0].Status)
	assert.Equal(t, "agent-service", attempts[0].Service)

	var task models.Task
	require.NoError(t, h.db.First(&task, "id = ?", taskID).Error)
	assert.Equal(t, models.TaskStatusCompleted, task.Status)
}

func TestRetryStageResetsTargetAndDownstreamStages(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusFailed, "PLAN")
	h.seedStages(taskID,
		stageSeed{Name: "PLAN", Status: models.StageStatusFailed},
		stageSeed{Name: "RTL_GEN", Status: models.StageStatusFailed},
	)

	require.NoError(t, h.service.RetryStage(context.Background(), taskID, "PLAN"))

	planStage := h.mustStage(taskID, "PLAN")
	rtlStage := h.mustStage(taskID, "RTL_GEN")
	assert.Equal(t, 1, planStage.RetryCount)
	assert.NotEqual(t, models.StageStatusFailed, planStage.Status)
	assert.NotEqual(t, models.StageStatusFailed, rtlStage.Status)
}

// The golden model is the reference the whole flow is built against, so
// GOLDEN_GEN must PARK on success and keep RTL_GEN out of the queue until a
// human accepts the output.
func TestGoldenGenAwaitsApprovalBeforeRTLGen(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusRunning, "GOLDEN_GEN")
	h.seedStages(taskID,
		stageSeed{Name: "PLAN", Status: models.StageStatusSucceeded},
		stageSeed{Name: "GOLDEN_GEN", Status: models.StageStatusQueued},
		stageSeed{Name: "RTL_GEN", Status: models.StageStatusNotStarted},
	)

	// Dispatch synchronously: driving this through evaluateTask's goroutine
	// races the shared in-memory SQLite handle, and a "table is locked" read
	// makes dispatchStage bail out silently — which would show up here as a
	// flake rather than as the behaviour under test.
	golden := h.mustStage(taskID, "GOLDEN_GEN")
	h.service.dispatchStage(context.Background(), taskID, golden.ID)

	assert.Equal(t, models.StageStatusAwaitingApproval, h.mustStage(taskID, "GOLDEN_GEN").Status,
		"a succeeded GOLDEN_GEN must park for human review, not go straight to SUCCEEDED")
	assert.Equal(t, models.StageStatusNotStarted, h.mustStage(taskID, "RTL_GEN").Status,
		"RTL_GEN must not start while the golden model is unreviewed")

	// The attempt itself succeeded — the hold is a gate, not a failure.
	var attempts []models.StageAttempt
	require.NoError(t, h.db.Where("task_id = ? AND stage_name = ?", taskID, "GOLDEN_GEN").Find(&attempts).Error)
	require.Len(t, attempts, 1)
	assert.Equal(t, models.StageStatusSucceeded, attempts[0].Status)

	require.NoError(t, h.service.ApproveStage(context.Background(), taskID, "golden_gen"))

	require.Eventually(t, func() bool {
		return h.mustStage(taskID, "GOLDEN_GEN").Status == models.StageStatusReleased &&
			h.mustStage(taskID, "RTL_GEN").Status == models.StageStatusSucceeded
	}, 4*time.Second, 50*time.Millisecond)
}

// Rejecting the gate has to DO something: the reviewer's correction is stored
// for the re-run and the stage goes back through the agent.
func TestRejectStageRecordsFeedbackAndRerunsStage(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusBlocked, "GOLDEN_GEN")
	h.seedStages(taskID,
		stageSeed{Name: "PLAN", Status: models.StageStatusSucceeded},
		stageSeed{Name: "GOLDEN_GEN", Status: models.StageStatusAwaitingApproval},
		stageSeed{Name: "RTL_GEN", Status: models.StageStatusNotStarted},
	)

	require.NoError(t, h.service.RejectStage(context.Background(), taskID,
		"golden_gen", "the sobel output is inverted — dark edges on white"))

	feedback := h.service.reviewFeedback(context.Background(), taskID, "GOLDEN_GEN")
	assert.Contains(t, feedback, "sobel output is inverted")

	stage := h.mustStage(taskID, "GOLDEN_GEN")
	assert.Equal(t, 1, stage.RetryCount)

	// The re-run lands back on the gate, and the correction rides along in the
	// prompt the agent receives.
	require.Eventually(t, func() bool {
		return h.mustStage(taskID, "GOLDEN_GEN").Status == models.StageStatusAwaitingApproval
	}, 3*time.Second, 50*time.Millisecond)
	assert.Equal(t, models.StageStatusNotStarted, h.mustStage(taskID, "RTL_GEN").Status)

	var task models.Task
	require.NoError(t, h.db.First(&task, "id = ?", taskID).Error)
	req := h.service.buildInvokeRequest(taskID, task, "GOLDEN_GEN", "Execute stage GOLDEN_GEN")
	assert.Contains(t, req.Prompt, "REVIEWER REJECTED")
	assert.Contains(t, req.Prompt, "sobel output is inverted")
}

func TestApproveStageReleasesGateAndAdvancesDownstream(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusBlocked, "SIGNOFF")
	h.seedStages(taskID,
		stageSeed{Name: "SIGNOFF", Status: models.StageStatusAwaitingApproval},
		stageSeed{Name: "EXPORT", Status: models.StageStatusNotStarted},
	)

	require.NoError(t, h.service.ApproveStage(context.Background(), taskID, "signoff"))

	require.Eventually(t, func() bool {
		return h.mustStage(taskID, "SIGNOFF").Status == models.StageStatusReleased &&
			h.mustStage(taskID, "EXPORT").Status == models.StageStatusSucceeded
	}, 4*time.Second, 50*time.Millisecond)

	var task models.Task
	require.NoError(t, h.db.First(&task, "id = ?", taskID).Error)
	assert.Equal(t, models.TaskStatusCompleted, task.Status)
}

// HW/SW verification sits BETWEEN simulation and hardening: it is the last
// stage that can still change the design cheaply, so nothing downstream may run
// until a human has accepted what the chip sent back.
func TestHwSwVerifyGatesHardening(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	defs := map[string]StageDefinition{}
	order := map[string]int{}
	for i, def := range h.service.Definitions() {
		defs[def.Name] = def
		order[def.Name] = i
	}

	stage, ok := defs["HW_SW_VERIFY"]
	require.True(t, ok, "HW_SW_VERIFY must be part of the pipeline")
	assert.Equal(t, []string{"SIM"}, stage.DependsOn)
	assert.True(t, stage.RequiresApproval, "the whole point of the stage is the human check")
	assert.Equal(t, []string{"HW_SW_VERIFY"}, defs["LINT"].DependsOn,
		"hardening must not start on a design whose hardware/software verification is unreviewed")
	assert.Greater(t, order["HW_SW_VERIFY"], order["SIM"])
	assert.Less(t, order["HW_SW_VERIFY"], order["SYNTH"])
	assert.Contains(t, reviewGateDetail("HW_SW_VERIFY"), "host interface",
		"each gate must describe what IT is asking, not the golden-model gate's question")
}

// A task created before a stage existed must still be able to run it — without
// this, adding a stage to the DAG could only ever affect brand-new tasks.
func TestEnsureStagesBackfillsAndRealignsExistingTasks(t *testing.T) {
	h := newSchedulerHarness(t)
	defer h.Close()

	taskID := uuid.NewString()
	h.seedTask(taskID, models.TaskStatusCompleted, "EXPORT")
	h.seedStages(taskID,
		stageSeed{Name: "SIM", Status: models.StageStatusReleased},
		// Seeded with the OLD edge (LINT used to hang off SIM directly).
		stageSeed{Name: "LINT", Status: models.StageStatusSucceeded, DependsOn: "SIM"},
		stageSeed{Name: "EXPORT", Status: models.StageStatusSucceeded},
	)

	require.NoError(t, h.service.EnsureStages(context.Background(), taskID))

	added := h.mustStage(taskID, "HW_SW_VERIFY")
	assert.Equal(t, models.StageStatusNotStarted, added.Status)
	assert.Equal(t, "SIM", added.DependsOn)
	assert.Equal(t, "HW_SW_VERIFY", h.mustStage(taskID, "LINT").DependsOn,
		"an existing stage's dependencies must be realigned with the current DAG")
	// Ordering follows the definitions so the timeline reads in flow order.
	assert.Less(t, h.mustStage(taskID, "SIM").SortOrder, added.SortOrder)
	assert.Less(t, added.SortOrder, h.mustStage(taskID, "LINT").SortOrder)

	// Idempotent: a second pass must not duplicate the row.
	require.NoError(t, h.service.EnsureStages(context.Background(), taskID))
	var rows []models.Stage
	require.NoError(t, h.db.Where("task_id = ? AND name = ?", taskID, "HW_SW_VERIFY").Find(&rows).Error)
	assert.Len(t, rows, 1)
}

type schedulerHarness struct {
	t           *testing.T
	db          *gorm.DB
	mini        *miniredis.Miniredis
	redisClient *redis.Client
	agentServer *httptest.Server
	service     *Service
}

type stageSeed struct {
	Name       string
	Status     models.StageStatus
	RetryCount int
	DependsOn  string
}

func newSchedulerHarness(t *testing.T) *schedulerHarness {
	t.Helper()

	db, err := gorm.Open(sqlite.Open("file:"+uuid.NewString()+"?mode=memory&cache=shared"), &gorm.Config{})
	require.NoError(t, err)
	require.NoError(t, db.AutoMigrate(&models.Task{}, &models.Stage{}, &models.StageAttempt{}))

	mini := miniredis.RunT(t)
	redisClient := redis.NewClient(&redis.Options{Addr: mini.Addr()})
	require.NoError(t, redisClient.Ping(context.Background()).Err())

	agentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status":           "success",
			"summary":          "mock agent completed stage",
			"diagnostics":      []map[string]any{},
			"artifacts":        []map[string]any{},
			"workspace_files":  map[string]string{"reports/mock.md": "ok"},
			"recommended_next": "Continue DAG",
		})
	}))

	service := NewService(db, redisClient, dispatcher.NewClient(agentServer.URL), nil)
	return &schedulerHarness{t: t, db: db, mini: mini, redisClient: redisClient, agentServer: agentServer, service: service}
}

func (h *schedulerHarness) Close() {
	h.agentServer.Close()
	_ = h.redisClient.Close()
	h.mini.Close()
}

func (h *schedulerHarness) seedTask(taskID string, status models.TaskStatus, currentStage string) {
	h.t.Helper()
	require.NoError(h.t, h.db.Create(&models.Task{
		ID:           taskID,
		Name:         "Scheduler Test",
		Slug:         "scheduler-test-" + taskID[:8],
		Description:  "scheduler coverage",
		DesignBrief:  "exercise stage transitions",
		LaunchMode:   models.LaunchModeFullFlowGated,
		RepoMode:     "TEMPLATE",
		RepoBranch:   "main",
		PDKID:        "sky130",
		StdcellLibID: "sky130_fd_sc_hd",
		OwnerID:      "user-1",
		OwnerName:    "Orchestrator Tester",
		Status:       status,
		CurrentStage: currentStage,
		AttemptCount: 1,
	}).Error)
}

func (h *schedulerHarness) seedStages(taskID string, stages ...stageSeed) {
	h.t.Helper()
	for idx, seed := range stages {
		dependsOn := seed.DependsOn
		if dependsOn == "" {
			dependsOn = strings.Join(h.dependsOn(seed.Name), ",")
		}
		require.NoError(h.t, h.db.Create(&models.Stage{
			ID:         uuid.NewString(),
			TaskID:     taskID,
			Name:       seed.Name,
			Status:     seed.Status,
			DependsOn:  dependsOn,
			SortOrder:  idx,
			RetryCount: seed.RetryCount,
		}).Error)
	}
}

func (h *schedulerHarness) dependsOn(name string) []string {
	for _, def := range h.service.Definitions() {
		if def.Name == name {
			return def.DependsOn
		}
	}
	return nil
}

func (h *schedulerHarness) mustStage(taskID, name string) models.Stage {
	h.t.Helper()
	var stage models.Stage
	require.NoError(h.t, h.db.First(&stage, "task_id = ? AND name = ?", taskID, name).Error)
	return stage
}

func TestMissingSlangFailureDetection(t *testing.T) {
	assert.True(t, isMissingSlangFailure("ERROR: Can't load module `./slang':\n/usr/local/lib/python3.12/site-packages/pyosys/share/plugins/slang.so: cannot open shared object file"))
	assert.False(t, isMissingSlangFailure("ERROR: unrelated LibreLane failure"))
	assert.Equal(t, "LibreLane slang plugin missing. Set USE_SLANG=false in config.", missingSlangFailureMessage())
}
