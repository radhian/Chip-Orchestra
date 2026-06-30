package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"chip-orchestra/orchestrator-service/internal/models"
	"chip-orchestra/orchestrator-service/internal/orchestrator"

	miniredis "github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTaskAPIIntegrationCreateGetAndPatchFlow(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db := newSQLiteDB(t)
	mini := miniredis.RunT(t)
	defer mini.Close()
	redisClient := redis.NewClient(&redis.Options{Addr: mini.Addr()})

	app := &App{
		DB:        db,
		Redis:     redisClient,
		Orch:      orchestrator.NewService(db, redisClient, nil, nil),
		JWTSecret: "integration-secret",
	}
	router := gin.New()
	app.RegisterRoutes(router)

	createPayload := map[string]any{
		"task": map[string]any{
			"name":         "Pipeline Integration",
			"description":  "Run full task API flow",
			"design_brief": "Smoke-test the task lifecycle",
			"launch_mode":  models.LaunchModeFullFlowGated,
			"review_gates": []string{"BEFORE_SIGNOFF"},
		},
	}

	createBody, err := json.Marshal(createPayload)
	require.NoError(t, err)

	createRec := httptest.NewRecorder()
	createReq := httptest.NewRequest(http.MethodPost, "/api/v1/tasks", bytes.NewReader(createBody))
	createReq.Header.Set("Content-Type", "application/json")
	createReq.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(createRec, createReq)

	require.Equal(t, http.StatusCreated, createRec.Code)

	var createResp map[string]any
	require.NoError(t, json.Unmarshal(createRec.Body.Bytes(), &createResp))
	taskID := createResp["task_id"].(string)
	require.NotEmpty(t, taskID)

	getRec := httptest.NewRecorder()
	getReq := httptest.NewRequest(http.MethodGet, "/api/v1/tasks/"+taskID, nil)
	getReq.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(getRec, getReq)

	require.Equal(t, http.StatusOK, getRec.Code)

	var getResp taskDetailResponse
	require.NoError(t, json.Unmarshal(getRec.Body.Bytes(), &getResp))
	assert.Equal(t, taskID, getResp.ID)
	assert.Equal(t, "Pipeline Integration", getResp.Name)
	assert.Equal(t, "SPEC_INGEST", getResp.CurrentStage)
	require.NotEmpty(t, getResp.Stages)

	patchPayload := map[string]any{
		"status":        models.TaskStatusRunning,
		"current_stage": "PLAN",
		"description":   "Updated from integration test",
	}
	patchBody, err := json.Marshal(patchPayload)
	require.NoError(t, err)

	patchRec := httptest.NewRecorder()
	patchReq := httptest.NewRequest(http.MethodPatch, "/api/v1/tasks/"+taskID, bytes.NewReader(patchBody))
	patchReq.Header.Set("Content-Type", "application/json")
	patchReq.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(patchRec, patchReq)

	require.Equal(t, http.StatusOK, patchRec.Code)

	var patchResp taskDetailResponse
	require.NoError(t, json.Unmarshal(patchRec.Body.Bytes(), &patchResp))
	assert.Equal(t, "Updated from integration test", patchResp.Description)
	assert.Equal(t, "PLAN", patchResp.CurrentStage)
	assert.Equal(t, "Running", patchResp.StatusLabel)

	var stored models.Task
	require.NoError(t, db.First(&stored, "id = ?", taskID).Error)
	assert.Equal(t, models.TaskStatusRunning, stored.Status)
	assert.Equal(t, "PLAN", stored.CurrentStage)
}
