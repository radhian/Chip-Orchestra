package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"chip-orchestra/operator-service/internal/dispatcher"
	"chip-orchestra/operator-service/internal/middleware"
	"chip-orchestra/operator-service/internal/models"
	"chip-orchestra/operator-service/internal/orchestrator"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
	"gorm.io/gorm"
)

type App struct {
	DB        *gorm.DB
	Redis     *redis.Client
	Orch      *orchestrator.Service
	Agent     *dispatcher.Client
	JWTSecret string
	Password  string
}

type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type createTaskBody struct {
	Task createTaskRequest `json:"task"`

	Name        string            `json:"name"`
	Description string            `json:"description"`
	DesignBrief string            `json:"design_brief"`
	LaunchMode  models.LaunchMode `json:"launch_mode"`
	Repo        struct {
		Mode       string `json:"mode"`
		TemplateID string `json:"template_id"`
	} `json:"repo"`
	DesignContext struct {
		PDKID        string `json:"pdk_id"`
		StdcellLibID string `json:"stdcell_lib_id"`
	} `json:"design_context"`
}

type createTaskRequest struct {
	Name         string            `json:"name"`
	Description  string            `json:"description"`
	DesignBrief  string            `json:"design_brief"`
	LaunchMode   models.LaunchMode `json:"launch_mode"`
	RepoID       string            `json:"repo_id"`
	RepoBranch   string            `json:"repo_branch"`
	RepoMode     string            `json:"repo_mode"`
	TemplateID   string            `json:"template_id"`
	PDKID        string            `json:"pdk_id"`
	StdcellLibID string            `json:"stdcell_lib_id"`
	ReviewGates  []string          `json:"review_gates"`
	OwnerID      string            `json:"owner_id"`
	OwnerName    string            `json:"owner_name"`
}

type patchTaskRequest struct {
	Description  *string            `json:"description"`
	Status       *models.TaskStatus `json:"status"`
	CurrentStage *string            `json:"current_stage"`
}

type stageView struct {
	Key             string `json:"key"`
	Label           string `json:"label"`
	Status          string `json:"status"`
	PendingApproval bool   `json:"pendingApproval,omitempty"`
}

type taskDetailResponse struct {
	ID                   string      `json:"id"`
	Name                 string      `json:"name"`
	Description          string      `json:"description"`
	OwnerName            string      `json:"ownerName"`
	OwnerID              string      `json:"ownerId"`
	CurrentStage         string      `json:"currentStage"`
	EtaLabel             string      `json:"etaLabel"`
	StatusLabel          string      `json:"statusLabel"`
	Tone                 string      `json:"tone"`
	RepoName             string      `json:"repoName"`
	PDKLabel             string      `json:"pdkLabel"`
	ReviewGateLabel      string      `json:"reviewGateLabel"`
	RuntimeLabel         string      `json:"runtimeLabel"`
	ArtifactLineageCount int         `json:"artifactLineageCount"`
	Stages               []stageView `json:"stages"`
	Attempts             []gin.H     `json:"attempts"`
}

func (a *App) RegisterRoutes(router *gin.Engine) {
	router.GET("/health", a.health)
	router.POST("/api/v1/auth/login", a.login)
	router.GET("/ws/tasks/:id/events", a.taskEventsWS)

	api := router.Group("/api/v1")
	api.Use(middleware.JWTAuth(a.JWTSecret))
	{
		api.GET("/auth/me", a.me)
		api.POST("/tasks", a.createTask)
		api.GET("/tasks", a.listTasks)
		api.GET("/tasks/:id", a.getTask)
		api.PATCH("/tasks/:id", a.patchTask)
		api.GET("/tasks/:id/stages", a.getStages)
		api.POST("/tasks/:id/stages/:stage/retry", a.retryStage)
		api.GET("/tasks/:id/attempts/latest/events", a.getEvents)
		api.GET("/tasks/:id/attempts/latest/artifacts", a.getArtifacts)
		api.GET("/tasks/:id/attempts/latest/diagnosis", a.getDiagnosis)
		api.GET("/tasks/:id/workspace/files", a.getWorkspaceFiles)
		api.GET("/tasks/:id/workspace/file", a.getWorkspaceFile)
		api.POST("/tasks/:id/workspace/propose-patch", a.proposePatch)
		api.GET("/tasks/:id/signoff/status", a.getSignoffStatus)
		api.POST("/tasks/:id/approvals/:stage", a.approveStage)
		api.POST("/tasks/:id/waivers", a.createWaiver)
		api.POST("/tasks/:id/export-bundle", a.exportBundle)
	}
}

func (a *App) health(c *gin.Context) {
	ctx := c.Request.Context()
	dbOK := a.DB.WithContext(ctx).Exec("SELECT 1").Error == nil
	redisOK := a.Redis.Ping(ctx).Err() == nil
	status := http.StatusOK
	if !dbOK || !redisOK {
		status = http.StatusServiceUnavailable
	}
	c.JSON(status, gin.H{"status": "ok", "database": dbOK, "redis": redisOK})
}

func (a *App) login(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var user models.User
	if err := a.DB.WithContext(c.Request.Context()).Where("username = ? OR email = ?", req.Username, req.Username).First(&user).Error; err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}
	if user.PasswordHash != middleware.HashPassword(req.Password) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}
	token, err := middleware.IssueToken(user, a.JWTSecret, time.Hour)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"access_token": token,
		"token_type":   "Bearer",
		"expires_in":   3600,
		"user": gin.H{
			"id":        user.ID,
			"username":  user.Username,
			"full_name": user.FullName,
			"roles":     strings.Split(user.Roles, ","),
		},
	})
}

func (a *App) me(c *gin.Context) {
	principal := c.MustGet("principal").(*middleware.JWTClaims)
	c.JSON(http.StatusOK, gin.H{"id": principal.UserID, "username": principal.Username, "full_name": principal.FullName, "roles": principal.Roles})
}

func (a *App) createTask(c *gin.Context) {
	var body createTaskBody
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	req := body.Task
	if req.Name == "" {
		req = createTaskRequest{
			Name:         body.Name,
			Description:  body.Description,
			DesignBrief:  body.DesignBrief,
			LaunchMode:   body.LaunchMode,
			RepoMode:     body.Repo.Mode,
			TemplateID:   body.Repo.TemplateID,
			PDKID:        body.DesignContext.PDKID,
			StdcellLibID: body.DesignContext.StdcellLibID,
			ReviewGates:  []string{"BEFORE_SIGNOFF"},
		}
		if req.LaunchMode == "" {
			req.LaunchMode = models.LaunchModeFullFlowGated
		}
		if req.RepoMode == "" {
			req.RepoMode = "TEMPLATE"
		}
	}
	principal := c.MustGet("principal").(*middleware.JWTClaims)
	if req.OwnerID == "" {
		req.OwnerID = principal.UserID
	}
	if req.OwnerName == "" {
		req.OwnerName = principal.FullName
	}

	task := models.Task{
		ID:           uuid.NewString(),
		Name:         req.Name,
		Slug:         slugify(req.Name),
		Description:  req.Description,
		DesignBrief:  req.DesignBrief,
		LaunchMode:   req.LaunchMode,
		RepoMode:     defaultString(req.RepoMode, "EXISTING"),
		RepoSource:   req.RepoID,
		RepoBranch:   defaultString(req.RepoBranch, "main"),
		TemplateID:   req.TemplateID,
		PDKID:        defaultString(req.PDKID, "sky130"),
		StdcellLibID: defaultString(req.StdcellLibID, "sky130_fd_sc_hd"),
		ReviewGates:  strings.Join(req.ReviewGates, ","),
		OwnerID:      req.OwnerID,
		OwnerName:    req.OwnerName,
		Status:       models.TaskStatusPending,
		CurrentStage: "SPEC_INGEST",
		EtaSeconds:   900,
		AttemptCount: 1,
	}
	if task.LaunchMode == "" {
		task.LaunchMode = models.LaunchModeFullFlowGated
	}

	if err := a.DB.WithContext(c.Request.Context()).Create(&task).Error; err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
		return
	}

	for idx, def := range a.Orch.Definitions() {
		stage := models.Stage{
			ID:        uuid.NewString(),
			TaskID:    task.ID,
			Name:      def.Name,
			Status:    models.StageStatusNotStarted,
			DependsOn: strings.Join(def.DependsOn, ","),
			SortOrder: idx,
		}
		if err := a.DB.WithContext(c.Request.Context()).Create(&stage).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
	}
	_ = a.Orch.QueueInitialStages(c.Request.Context(), task.ID)
	c.JSON(http.StatusCreated, gin.H{"task_id": task.ID, "id": task.ID, "attempt_id": fmt.Sprintf("%s-attempt-1", task.ID), "status": task.Status, "current_stage": task.CurrentStage, "created_at": task.CreatedAt})
}

func (a *App) listTasks(c *gin.Context) {
	query := a.DB.WithContext(c.Request.Context()).Model(&models.Task{})
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}
	if stage := c.Query("stage"); stage != "" {
		query = query.Where("current_stage = ?", stage)
	}
	var tasks []models.Task
	if err := query.Order("updated_at desc").Find(&tasks).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]gin.H, 0, len(tasks))
	for _, task := range tasks {
		items = append(items, gin.H{
			"task_id":        task.ID,
			"id":             task.ID,
			"name":           task.Name,
			"description":    defaultString(task.Description, "Task-centric design object with artifact lineage"),
			"status":         task.Status,
			"statusLabel":    strings.Title(strings.ToLower(string(task.Status))),
			"tone":           statusTone(task.Status),
			"current_stage":  task.CurrentStage,
			"currentStage":   task.CurrentStage,
			"owner":          gin.H{"id": task.OwnerID, "full_name": task.OwnerName},
			"ownerName":      task.OwnerName,
			"ownerId":        task.OwnerID,
			"latest_attempt": task.AttemptCount,
			"eta_seconds":    task.EtaSeconds,
			"etaLabel":       etaLabel(task.EtaSeconds),
			"repoName":       defaultString(task.RepoSource, task.TemplateID),
			"updated_at":     task.UpdatedAt,
		})
	}
	c.JSON(http.StatusOK, gin.H{"items": items, "next_cursor": ""})
}

func (a *App) getTask(c *gin.Context) {
	var task models.Task
	if err := a.DB.WithContext(c.Request.Context()).First(&task, "id = ?", c.Param("id")).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	var stages []models.Stage
	_ = a.DB.WithContext(c.Request.Context()).Where("task_id = ?", task.ID).Order("sort_order asc").Find(&stages).Error
	var attempts []models.StageAttempt
	_ = a.DB.WithContext(c.Request.Context()).Where("task_id = ?", task.ID).Order("created_at desc").Find(&attempts).Error
	resp := taskDetailResponse{
		ID:                   task.ID,
		Name:                 task.Name,
		Description:          task.Description,
		OwnerName:            task.OwnerName,
		OwnerID:              task.OwnerID,
		CurrentStage:         task.CurrentStage,
		EtaLabel:             etaLabel(task.EtaSeconds),
		StatusLabel:          strings.Title(strings.ToLower(string(task.Status))),
		Tone:                 statusTone(task.Status),
		RepoName:             defaultString(task.RepoSource, task.TemplateID),
		PDKLabel:             fmt.Sprintf("%s / %s", task.PDKID, task.StdcellLibID),
		ReviewGateLabel:      reviewGateLabel(task.ReviewGates),
		RuntimeLabel:         "Orchestrator Service + Agent Service + EDA Service",
		ArtifactLineageCount: a.listLength(c.Request.Context(), fmt.Sprintf("task:%s:artifacts", task.ID)),
		Stages:               make([]stageView, 0, len(stages)),
		Attempts:             make([]gin.H, 0),
	}
	for _, stage := range stages {
		resp.Stages = append(resp.Stages, stageView{Key: strings.ToLower(stage.Name), Label: humanizeStage(stage.Name), Status: stageTimelineStatus(stage.Status), PendingApproval: stage.Status == models.StageStatusAwaitingApproval})
	}
	for _, attempt := range attempts {
		resp.Attempts = append(resp.Attempts, gin.H{"id": attempt.ID, "status": strings.ToLower(string(attempt.Status)), "startedAt": attempt.CreatedAt.Format(time.Kitchen), "updatedAt": attempt.UpdatedAt.Format(time.Kitchen)})
		if len(resp.Attempts) == 3 {
			break
		}
	}
	c.JSON(http.StatusOK, resp)
}

func (a *App) patchTask(c *gin.Context) {
	var req patchTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	updates := map[string]any{}
	if req.Description != nil {
		updates["description"] = *req.Description
	}
	if req.Status != nil {
		updates["status"] = *req.Status
	}
	if req.CurrentStage != nil {
		updates["current_stage"] = *req.CurrentStage
	}
	if len(updates) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "no updates provided"})
		return
	}
	if err := a.DB.WithContext(c.Request.Context()).Model(&models.Task{}).Where("id = ?", c.Param("id")).Updates(updates).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	a.getTask(c)
}

func (a *App) getStages(c *gin.Context) {
	var stages []models.Stage
	if err := a.DB.WithContext(c.Request.Context()).Where("task_id = ?", c.Param("id")).Order("sort_order asc").Find(&stages).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]gin.H, 0, len(stages))
	for _, stage := range stages {
		dependsOn := []string{}
		if stage.DependsOn != "" {
			dependsOn = strings.Split(stage.DependsOn, ",")
		}
		items = append(items, gin.H{"stage_id": stage.ID, "name": stage.Name, "status": stage.Status, "depends_on": dependsOn, "retry_count": stage.RetryCount, "started_at": stage.StartedAt})
	}
	c.JSON(http.StatusOK, gin.H{"task_id": c.Param("id"), "stages": items})
}

func (a *App) retryStage(c *gin.Context) {
	stageName := strings.ToUpper(c.Param("stage"))
	if err := a.Orch.RetryStage(c.Request.Context(), c.Param("id"), stageName); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "queued", "stage": stageName})
}

func (a *App) getEvents(c *gin.Context) {
	c.JSON(http.StatusOK, a.readJSONList(c.Request.Context(), fmt.Sprintf("task:%s:events", c.Param("id"))))
}

func (a *App) getArtifacts(c *gin.Context) {
	c.JSON(http.StatusOK, a.readJSONList(c.Request.Context(), fmt.Sprintf("task:%s:artifacts", c.Param("id"))))
}

func (a *App) getDiagnosis(c *gin.Context) {
	c.JSON(http.StatusOK, a.readJSONList(c.Request.Context(), fmt.Sprintf("task:%s:diagnosis", c.Param("id"))))
}

func (a *App) getWorkspaceFiles(c *gin.Context) {
	entries, err := a.Redis.HGetAll(c.Request.Context(), fmt.Sprintf("task:%s:workspace:index", c.Param("id"))).Result()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	items := make([]gin.H, 0, len(entries))
	for path, note := range entries {
		parts := strings.Split(path, "/")
		items = append(items, gin.H{"path": path, "name": parts[len(parts)-1], "note": note, "status": "Updated"})
	}
	sort.Slice(items, func(i, j int) bool { return items[i]["path"].(string) < items[j]["path"].(string) })
	c.JSON(http.StatusOK, items)
}

func (a *App) getWorkspaceFile(c *gin.Context) {
	path := c.Query("path")
	content, err := a.Redis.Get(c.Request.Context(), fmt.Sprintf("task:%s:workspace:file:%s", c.Param("id"), path)).Result()
	if err == redis.Nil {
		c.JSON(http.StatusOK, gin.H{"path": path, "content": "// File not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"path": path, "content": content})
}

func (a *App) proposePatch(c *gin.Context) {
	var req struct {
		Instruction string `json:"instruction"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	resp, err := a.Agent.Invoke(c.Request.Context(), dispatcher.InvokeRequest{TaskID: c.Param("id"), Stage: "FLOW_ASSISTANT", Prompt: req.Instruction, Tools: []string{"write_artifact"}, Context: map[string]any{"mode": "patch"}})
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	for path, content := range resp.WorkspaceFiles {
		_ = a.Redis.Set(c.Request.Context(), fmt.Sprintf("task:%s:workspace:file:%s", c.Param("id"), path), content, 0).Err()
		_ = a.Redis.HSet(c.Request.Context(), fmt.Sprintf("task:%s:workspace:index", c.Param("id")), path, "generated by Flow Assistant").Err()
	}
	_ = a.Redis.RPush(c.Request.Context(), fmt.Sprintf("task:%s:events", c.Param("id")), fmt.Sprintf(`{"id":"%s","time":"%s","title":"Patch proposal queued","detail":%q,"tone":"info"}`, uuid.NewString(), time.Now().Format("15:04"), resp.Summary)).Err()
	c.JSON(http.StatusOK, gin.H{"status": "queued", "recommended_next": resp.RecommendedNext})
}

func (a *App) getSignoffStatus(c *gin.Context) {
	var stages []models.Stage
	_ = a.DB.WithContext(c.Request.Context()).Where("task_id = ?", c.Param("id")).Find(&stages).Error
	signoffDone := false
	for _, stage := range stages {
		if stage.Name == "SIGNOFF" && (stage.Status == models.StageStatusReleased || stage.Status == models.StageStatusSucceeded) {
			signoffDone = true
		}
	}
	c.JSON(http.StatusOK, gin.H{
		"stateLabel":      ternary(signoffDone, "Approved", "Awaiting final approval"),
		"message":         ternary(signoffDone, "Signoff is approved and the export bundle can be delivered.", "The task remains blocked on final signoff approval."),
		"packageContents": []string{"Final RTL snapshot and verification bundle", "EDA timing and implementation reports", "Approval trail with operator review metadata"},
		"checklist":       []gin.H{{"id": "signoff-1", "label": "DRC/LVS package ready", "detail": "Mock signoff package prepared by the EDA Service.", "done": signoffDone}, {"id": "signoff-2", "label": "Power and timing guardrail accepted", "detail": "Review the latest synthesized report before release.", "done": signoffDone}, {"id": "signoff-3", "label": "Tapeout handoff approved", "detail": "Operator approval is required to release EXPORT.", "done": signoffDone}},
	})
}

func (a *App) approveStage(c *gin.Context) {
	if err := a.Orch.ApproveStage(c.Request.Context(), c.Param("id"), c.Param("stage")); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "recorded"})
}

func (a *App) createWaiver(c *gin.Context) {
	var req map[string]any
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	payload, _ := json.Marshal(gin.H{"id": uuid.NewString(), "time": time.Now().Format("15:04"), "title": fmt.Sprintf("Waiver requested: %v", req["title"]), "detail": req["detail"], "tone": "warning"})
	_ = a.Redis.RPush(c.Request.Context(), fmt.Sprintf("task:%s:events", c.Param("id")), payload).Err()
	c.JSON(http.StatusOK, gin.H{"status": "queued"})
}

func (a *App) exportBundle(c *gin.Context) {
	artifact := gin.H{"id": uuid.NewString(), "name": "chip_orchestra_export_bundle.zip", "type": "EXPORT_BUNDLE", "owner": "Orchestrator Service"}
	payload, _ := json.Marshal(artifact)
	_ = a.Redis.RPush(c.Request.Context(), fmt.Sprintf("task:%s:artifacts", c.Param("id")), payload).Err()
	c.JSON(http.StatusOK, gin.H{"artifactId": artifact["id"], "status": "queued"})
}

var upgrader = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}

func (a *App) taskEventsWS(c *gin.Context) {
	if !a.wsAuthorized(c.Request) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing or invalid token"})
		return
	}
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		return
	}
	defer conn.Close()

	ctx, cancel := context.WithCancel(c.Request.Context())
	defer cancel()
	pubsub := a.Redis.Subscribe(ctx, fmt.Sprintf("task:%s:events:pubsub", c.Param("id")))
	defer pubsub.Close()
	channel := pubsub.Channel()

	for {
		select {
		case <-ctx.Done():
			return
		case msg := <-channel:
			if msg == nil {
				return
			}
			if err := conn.WriteMessage(websocket.TextMessage, []byte(msg.Payload)); err != nil {
				return
			}
		}
	}
}

func (a *App) wsAuthorized(r *http.Request) bool {
	token := r.URL.Query().Get("token")
	if token == "" {
		auth := r.Header.Get("Authorization")
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) == 2 {
			token = parts[1]
		}
	}
	if token == "" {
		return false
	}
	parsed, err := jwt.Parse(token, func(token *jwt.Token) (interface{}, error) { return []byte(a.JWTSecret), nil })
	return err == nil && parsed.Valid
}

func (a *App) readJSONList(ctx context.Context, key string) []map[string]any {
	items, err := a.Redis.LRange(ctx, key, 0, -1).Result()
	if err != nil {
		return []map[string]any{}
	}
	result := make([]map[string]any, 0, len(items))
	for _, item := range items {
		entry := map[string]any{}
		if err := json.Unmarshal([]byte(item), &entry); err == nil {
			result = append(result, entry)
		}
	}
	return result
}

func (a *App) listLength(ctx context.Context, key string) int {
	count, err := a.Redis.LLen(ctx, key).Result()
	if err != nil {
		return 0
	}
	return int(count)
}

func defaultString(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}

func slugify(raw string) string {
	lower := strings.ToLower(strings.TrimSpace(raw))
	lower = strings.ReplaceAll(lower, " ", "-")
	builder := strings.Builder{}
	for _, ch := range lower {
		if (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '-' {
			builder.WriteRune(ch)
		} else {
			builder.WriteRune('-')
		}
	}
	out := strings.Trim(builder.String(), "-")
	if out == "" {
		return "task-" + time.Now().Format("20060102150405")
	}
	return out
}

func statusTone(status models.TaskStatus) string {
	switch status {
	case models.TaskStatusCompleted:
		return "passed"
	case models.TaskStatusFailed:
		return "failed"
	case models.TaskStatusBlocked:
		return "review"
	default:
		return "running"
	}
}

func etaLabel(seconds int) string {
	if seconds <= 0 {
		return "Ready"
	}
	return fmt.Sprintf("%d min", seconds/60)
}

func humanizeStage(name string) string {
	return strings.Title(strings.ToLower(strings.ReplaceAll(name, "_", " ")))
}

func reviewGateLabel(raw string) string {
	if strings.Contains(raw, "BEFORE_SYNTH") && strings.Contains(raw, "BEFORE_SIGNOFF") {
		return "Human approval required before synthesis and signoff"
	}
	if strings.Contains(raw, "BEFORE_SYNTH") {
		return "Human approval required before synthesis"
	}
	return "Human approval required before signoff package"
}

func stageTimelineStatus(status models.StageStatus) string {
	switch status {
	case models.StageStatusSucceeded, models.StageStatusReleased:
		return "done"
	case models.StageStatusRunning, models.StageStatusDispatching:
		return "active"
	case models.StageStatusFailed:
		return "failed"
	default:
		return "queued"
	}
}

func ternary[T any](condition bool, yes, no T) T {
	if condition {
		return yes
	}
	return no
}
