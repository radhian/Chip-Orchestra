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
