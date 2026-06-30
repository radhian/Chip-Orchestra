package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"chip-orchestra/orchestrator-service/internal/middleware"
	"chip-orchestra/orchestrator-service/internal/models"
	"chip-orchestra/orchestrator-service/internal/orchestrator"

	sqlmock "github.com/DATA-DOG/go-sqlmock"
	miniredis "github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/mysql"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestCreateTaskHandlerCreatesTaskAndInitialStage(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db := newSQLiteDB(t)
	mini, redisClient := newMiniRedis(t)
	defer mini.Close()

	app := &App{
		DB:        db,
		Redis:     redisClient,
		Orch:      orchestrator.NewService(db, redisClient, nil, nil),
		JWTSecret: "unit-secret",
	}
	router := gin.New()
	app.RegisterRoutes(router)

	body := createTaskBody{
		Task: createTaskRequest{
			Name:        "ALU Build",
			Description: "Create an ALU",
			DesignBrief: "Implement a 32-bit ALU",
			LaunchMode:  models.LaunchModeFullFlowGated,
			ReviewGates: []string{"BEFORE_SIGNOFF"},
		},
	}
	payload, err := json.Marshal(body)
	require.NoError(t, err)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/tasks", bytes.NewReader(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusCreated, rec.Code)

	var response map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &response))
	taskID, ok := response["task_id"].(string)
	require.True(t, ok)
	require.NotEmpty(t, taskID)

	var task models.Task
	require.NoError(t, db.First(&task, "id = ?", taskID).Error)
	assert.Equal(t, "alu-build", task.Slug)
	assert.Equal(t, models.TaskStatusPending, task.Status)
	assert.Equal(t, "SPEC_INGEST", task.CurrentStage)
	assert.Equal(t, "user-1", task.OwnerID)
	assert.Equal(t, "Orchestrator Tester", task.OwnerName)

	var stage models.Stage
	require.NoError(t, db.First(&stage, "task_id = ? AND name = ?", taskID, "SPEC_INGEST").Error)
	assert.Equal(t, models.StageStatusQueued, stage.Status)

	events, err := redisClient.LLen(req.Context(), "task:"+taskID+":events").Result()
	require.NoError(t, err)
	assert.GreaterOrEqual(t, events, int64(1))
}

func TestListTasksHandlerReturnsTaskCollection(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db, mock, cleanup := newMockDB(t)
	defer cleanup()
	mini, redisClient := newMiniRedis(t)
	defer mini.Close()

	now := time.Now().UTC()
	mock.ExpectQuery("SELECT .* FROM `tasks` ORDER BY updated_at desc").WillReturnRows(
		sqlmock.NewRows(taskColumns()).AddRow(
			"task-1",
			"ALU Build",
			"alu-build",
			"Create an ALU",
			"Implement a 32-bit ALU",
			string(models.LaunchModeFullFlowGated),
			"TEMPLATE",
			"template://alu",
			"main",
			"tmpl-1",
			"sky130",
			"sky130_fd_sc_hd",
			"BEFORE_SIGNOFF",
			"user-1",
			"Orchestrator Tester",
			string(models.TaskStatusRunning),
			"PLAN",
			"",
			600,
			1,
			now,
			now,
		),
	)

	app := &App{DB: db, Redis: redisClient, Orch: &orchestrator.Service{}, JWTSecret: "unit-secret"}
	router := gin.New()
	app.RegisterRoutes(router)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/tasks", nil)
	req.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)
	assert.NoError(t, mock.ExpectationsWereMet())

	var response struct {
		Items []map[string]any `json:"items"`
	}
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &response))
	require.Len(t, response.Items, 1)
	assert.Equal(t, "ALU Build", response.Items[0]["name"])
	assert.Equal(t, "PLAN", response.Items[0]["current_stage"])
	assert.Equal(t, "Running", response.Items[0]["statusLabel"])
}

func TestGetTaskHandlerReturnsNotFound(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db, mock, cleanup := newMockDB(t)
	defer cleanup()
	mini, redisClient := newMiniRedis(t)
	defer mini.Close()

	mock.ExpectQuery("SELECT .* FROM `tasks` WHERE id = .*LIMIT .*").
		WithArgs("missing", sqlmock.AnyArg()).
		WillReturnRows(sqlmock.NewRows(taskColumns()))

	app := &App{DB: db, Redis: redisClient, Orch: &orchestrator.Service{}, JWTSecret: "unit-secret"}
	router := gin.New()
	app.RegisterRoutes(router)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/tasks/missing", nil)
	req.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusNotFound, rec.Code)
	assert.NoError(t, mock.ExpectationsWereMet())
	assert.Contains(t, rec.Body.String(), "task not found")
}

func TestPatchTaskHandlerRejectsEmptyUpdate(t *testing.T) {
	gin.SetMode(gin.TestMode)

	db := newSQLiteDB(t)
	mini, redisClient := newMiniRedis(t)
	defer mini.Close()

	app := &App{DB: db, Redis: redisClient, Orch: &orchestrator.Service{}, JWTSecret: "unit-secret"}
	router := gin.New()
	app.RegisterRoutes(router)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPatch, "/api/v1/tasks/task-1", bytes.NewBufferString(`{}`))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", bearerToken(t, app.JWTSecret))
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusBadRequest, rec.Code)
	assert.Contains(t, rec.Body.String(), "no updates provided")
}

func newSQLiteDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open("file:"+uuid.NewString()+"?mode=memory&cache=shared"), &gorm.Config{})
	require.NoError(t, err)
	require.NoError(t, db.AutoMigrate(&models.Task{}, &models.Stage{}, &models.StageAttempt{}, &models.User{}))
	return db
}

func newMockDB(t *testing.T) (*gorm.DB, sqlmock.Sqlmock, func()) {
	t.Helper()
	sqlDB, mock, err := sqlmock.New()
	require.NoError(t, err)

	db, err := gorm.Open(mysql.New(mysql.Config{Conn: sqlDB, SkipInitializeWithVersion: true}), &gorm.Config{})
	require.NoError(t, err)

	cleanup := func() {
		_ = sqlDB.Close()
	}
	return db, mock, cleanup
}

func newMiniRedis(t *testing.T) (*miniredis.Miniredis, *redis.Client) {
	t.Helper()
	mini := miniredis.RunT(t)
	client := redis.NewClient(&redis.Options{Addr: mini.Addr()})
	require.NoError(t, client.Ping(context.Background()).Err())
	return mini, client
}

func bearerToken(t *testing.T, secret string) string {
	t.Helper()
	token, err := middleware.IssueToken(models.User{
		ID:       "user-1",
		Username: "orchestrator.tester",
		FullName: "Orchestrator Tester",
		Roles:    string(models.UserRoleAdmin),
	}, secret, time.Hour)
	require.NoError(t, err)
	return "Bearer " + token
}

func taskColumns() []string {
	return []string{
		"id",
		"name",
		"slug",
		"description",
		"design_brief",
		"launch_mode",
		"repo_mode",
		"repo_source",
		"repo_branch",
		"template_id",
		"pdk_id",
		"stdcell_lib_id",
		"review_gates",
		"owner_id",
		"owner_name",
		"status",
		"current_stage",
		"last_error",
		"eta_seconds",
		"attempt_count",
		"created_at",
		"updated_at",
	}
}
