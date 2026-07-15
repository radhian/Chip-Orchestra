package api

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"chip-orchestra/orchestrator-service/internal/dispatcher"
	"chip-orchestra/orchestrator-service/internal/middleware"
	"chip-orchestra/orchestrator-service/internal/models"
	"chip-orchestra/orchestrator-service/internal/orchestrator"

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

// taskAttachment is a user-uploaded file (image / PDF / text) sent base64 with
// the create-task request. It is written into the task workspace at
// context/uploads/ BEFORE the first stage runs, so the agent service can build
// the vision digest of it.
type taskAttachment struct {
	Name          string `json:"name"`
	ContentBase64 string `json:"content_base64"`
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
	LLMModel    string           `json:"llm_model"`
	Attachments []taskAttachment `json:"attachments"`
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
	LLMModel     string            `json:"llm_model"`
	ReviewGates  []string          `json:"review_gates"`
	OwnerID      string            `json:"owner_id"`
	OwnerName    string            `json:"owner_name"`
	Attachments  []taskAttachment  `json:"attachments"`
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
		api.GET("/llm/models", a.llmModels)
		api.POST("/tasks", a.createTask)
		api.GET("/tasks", a.listTasks)
		api.GET("/tasks/:id", a.getTask)
		api.PATCH("/tasks/:id", a.patchTask)
		api.DELETE("/tasks/:id", a.deleteTask)
		api.GET("/tasks/:id/stages", a.getStages)
		api.POST("/tasks/:id/stages/:stage/retry", a.retryStage)
		api.GET("/tasks/:id/attempts/latest/events", a.getEvents)
		api.GET("/tasks/:id/attempts/latest/artifacts", a.getArtifacts)
		api.GET("/tasks/:id/attempts/latest/diagnosis", a.getDiagnosis)
		api.GET("/tasks/:id/workspace/files", a.getWorkspaceFiles)
		api.GET("/tasks/:id/workspace/file", a.getWorkspaceFile)
		api.GET("/tasks/:id/workspace/raw", a.getWorkspaceRaw)
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
	// 24h token: image/download URLs embed the JWT (`?token=`), and a 1-hour
	// expiry made every <img> in a long-open tab break with 401s.
	token, err := middleware.IssueToken(user, a.JWTSecret, 24*time.Hour)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"access_token": token,
		"token_type":   "Bearer",
		"expires_in":   86400,
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

func (a *App) deleteTask(c *gin.Context) {
	ctx := c.Request.Context()
	var task models.Task
	if err := a.DB.WithContext(ctx).First(&task, "id = ?", c.Param("id")).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}
	if err := a.DB.WithContext(ctx).Where("task_id = ?", task.ID).Delete(&models.StageAttempt{}).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := a.DB.WithContext(ctx).Where("task_id = ?", task.ID).Delete(&models.Stage{}).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if err := a.DB.WithContext(ctx).Delete(&task).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "deleted", "task_id": task.ID})
}

func (a *App) llmModels(c *gin.Context) {
	models, err := a.Agent.Models(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, models)
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
			LLMModel:     body.LLMModel,
			ReviewGates:  []string{"BEFORE_SIGNOFF"},
			Attachments:  body.Attachments,
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
		LLMModel:     req.LLMModel,
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

	// Persist user attachments (images / PDFs / specs) into the shared task
	// workspace BEFORE any stage is queued, so the agent service's vision
	// digest sees them on the very first stage.
	if len(req.Attachments) > 0 {
		if err := a.saveTaskAttachments(task.ID, req.Attachments); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("failed to store attachments: %v", err)})
			return
		}
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

// saveTaskAttachments decodes base64 uploads and writes them under the task
// workspace's context/uploads/ directory (marking images as REAL user uploads
// via .user_images.txt, matching the agent service's convention).
func (a *App) saveTaskAttachments(taskID string, attachments []taskAttachment) error {
	updir := filepath.Join(a.Orch.TaskWorkspace(taskID), "context", "uploads")
	if err := os.MkdirAll(updir, 0o755); err != nil {
		return err
	}
	sanitize := regexp.MustCompile(`[^\w.\-]`)
	imageExt := map[string]bool{".png": true, ".jpg": true, ".jpeg": true, ".webp": true, ".bmp": true, ".gif": true}
	var imageNames []string
	for _, att := range attachments {
		name := sanitize.ReplaceAllString(filepath.Base(att.Name), "_")
		if name == "" || name == "." {
			continue
		}
		data, err := base64.StdEncoding.DecodeString(att.ContentBase64)
		if err != nil {
			return fmt.Errorf("attachment %q is not valid base64: %w", att.Name, err)
		}
		if len(data) > 32<<20 {
			return fmt.Errorf("attachment %q exceeds the 32 MB limit", att.Name)
		}
		if err := os.WriteFile(filepath.Join(updir, name), data, 0o644); err != nil {
			return err
		}
		if imageExt[strings.ToLower(filepath.Ext(name))] {
			imageNames = append(imageNames, name)
		}
	}
	if len(imageNames) > 0 {
		f, err := os.OpenFile(filepath.Join(updir, ".user_images.txt"), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
		if err == nil {
			defer f.Close()
			_, _ = f.WriteString(strings.Join(imageNames, "\n") + "\n")
		}
	}
	return nil
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
			"etaLabel":       etaLabel(task),
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
		EtaLabel:             stagesEtaLabel(task, stages),
		StatusLabel:          strings.Title(strings.ToLower(string(task.Status))),
		Tone:                 statusTone(task.Status),
		RepoName:             defaultString(task.RepoSource, task.TemplateID),
		PDKLabel:             fmt.Sprintf("%s / %s", task.PDKID, task.StdcellLibID),
		ReviewGateLabel:      reviewGateLabel(task.ReviewGates),
		RuntimeLabel:         "Orchestrator Service + Agent Service + EDA Service",
		ArtifactLineageCount: len(a.readTaskArtifacts(c.Request.Context(), task.ID)),
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
	// A MANUAL retry re-arms the SIM auto-repair budget (the automatic loop
	// must never reset its own counter).
	a.Orch.ResetSimRepairBudget(c.Request.Context(), c.Param("id"))
	if err := a.Orch.RetryStage(c.Request.Context(), c.Param("id"), stageName); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "queued", "stage": stageName})
}

func (a *App) getEvents(c *gin.Context) {
	events := a.readJSONList(c.Request.Context(), fmt.Sprintf("task:%s:events", c.Param("id")))
	// Legacy stage.updated events (recorded before events carried display
	// fields) have no title and rendered as EMPTY rows — drop them.
	filtered := make([]map[string]any, 0, len(events))
	for _, event := range events {
		if title, _ := event["title"].(string); title != "" {
			filtered = append(filtered, event)
		}
	}
	c.JSON(http.StatusOK, filtered)
}

func (a *App) getArtifacts(c *gin.Context) {
	taskID := c.Param("id")
	artifacts := a.readTaskArtifacts(c.Request.Context(), taskID)
	// Backfill `path` for legacy artifact records (stored before artifacts
	// carried their workspace-relative path): find a workspace file whose
	// basename matches the artifact name so the UI can open it instead of
	// showing "Unavailable".
	needsPath := false
	for _, art := range artifacts {
		if p, _ := art["path"].(string); p == "" {
			needsPath = true
			break
		}
	}
	if needsPath {
		byName := map[string]string{}
		workspace := a.Orch.TaskWorkspace(taskID)
		if info, err := os.Stat(workspace); err == nil && info.IsDir() {
			_ = filepath.Walk(workspace, func(p string, info os.FileInfo, err error) error {
				if err != nil || info.IsDir() {
					return nil
				}
				if rel, relErr := filepath.Rel(workspace, p); relErr == nil {
					if _, exists := byName[info.Name()]; !exists {
						byName[info.Name()] = filepath.ToSlash(rel)
					}
				}
				return nil
			})
		}
		for _, art := range artifacts {
			if p, _ := art["path"].(string); p == "" {
				if name, _ := art["name"].(string); name != "" {
					if rel, exists := byName[name]; exists {
						art["path"] = rel
					}
				}
			}
		}
	}
	c.JSON(http.StatusOK, artifacts)
}

func (a *App) getDiagnosis(c *gin.Context) {
	c.JSON(http.StatusOK, a.readJSONList(c.Request.Context(), fmt.Sprintf("task:%s:diagnosis", c.Param("id"))))
}

// getWorkspaceFiles lists the task's files from the SHARED WORKSPACE ON DISK
// (the source of truth — the deep agents and eda-service write files there
// directly), merged with the Redis index kept for stage-generated notes. The
// old Redis-only listing is why artifacts existed on disk yet showed as
// missing/unavailable in the UI.
func (a *App) getWorkspaceFiles(c *gin.Context) {
	taskID := c.Param("id")
	seen := map[string]string{}

	workspace := a.Orch.TaskWorkspace(taskID)
	if info, err := os.Stat(workspace); err == nil && info.IsDir() {
		_ = filepath.Walk(workspace, func(p string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}
			if info.Size() > 32<<20 { // skip huge binaries (GDS streams etc.)
				return nil
			}
			rel, relErr := filepath.Rel(workspace, p)
			if relErr != nil {
				return nil
			}
			rel = filepath.ToSlash(rel)
			// hidden files and the python sandbox scratch dir are noise
			if strings.HasPrefix(filepath.Base(rel), ".") || strings.HasPrefix(rel, "work/") {
				return nil
			}
			seen[rel] = "workspace file"
			return nil
		})
	}

	entries, err := a.Redis.HGetAll(c.Request.Context(), fmt.Sprintf("task:%s:workspace:index", taskID)).Result()
	if err == nil {
		for path, note := range entries {
			seen[path] = note
		}
	}

	items := make([]gin.H, 0, len(seen))
	for path, note := range seen {
		parts := strings.Split(path, "/")
		items = append(items, gin.H{"path": path, "name": parts[len(parts)-1], "note": note, "status": "Updated"})
	}
	sort.Slice(items, func(i, j int) bool { return items[i]["path"].(string) < items[j]["path"].(string) })
	c.JSON(http.StatusOK, items)
}

var binaryFileRE = regexp.MustCompile(`(?i)\.(png|jpe?g|webp|bmp|gif|gds2?|oas|pdf|vcd|fst|zip|gz|tar|bin|lef|def|spef|db)$`)

// getWorkspaceFile serves a TEXT file DISK-FIRST from the shared workspace,
// falling back to the Redis copy for legacy entries. Binary files (images,
// GDS, waves) are not dumped as garbage text — the client should use
// /workspace/raw for those.
func (a *App) getWorkspaceFile(c *gin.Context) {
	taskID := c.Param("id")
	path := c.Query("path")
	if binaryFileRE.MatchString(path) {
		c.JSON(http.StatusOK, gin.H{"path": path, "content": fmt.Sprintf("// binary file — download it via /api/v1/tasks/%s/workspace/raw?path=%s", taskID, path)})
		return
	}
	if path != "" && !strings.Contains(path, "..") && !filepath.IsAbs(path) {
		full := filepath.Join(a.Orch.TaskWorkspace(taskID), filepath.FromSlash(path))
		if info, err := os.Stat(full); err == nil && !info.IsDir() && info.Size() <= 32<<20 {
			data, readErr := os.ReadFile(full)
			if readErr == nil {
				c.JSON(http.StatusOK, gin.H{"path": path, "content": string(data)})
				return
			}
		}
	}
	content, err := a.Redis.Get(c.Request.Context(), fmt.Sprintf("task:%s:workspace:file:%s", taskID, path)).Result()
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

// getWorkspaceRaw streams a workspace file as raw bytes with its native
// content type — what <img src> and browser download links need (auth via the
// `?token=` JWT fallback). Text views should keep using /workspace/file.
func (a *App) getWorkspaceRaw(c *gin.Context) {
	path := c.Query("path")
	if path == "" || strings.Contains(path, "..") || filepath.IsAbs(path) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid path"})
		return
	}
	full := filepath.Join(a.Orch.TaskWorkspace(c.Param("id")), filepath.FromSlash(path))
	info, err := os.Stat(full)
	if err != nil || info.IsDir() {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}
	if c.Query("download") != "" {
		c.FileAttachment(full, filepath.Base(full))
		return
	}
	c.File(full)
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
	taskID := c.Param("id")
	var stages []models.Stage
	_ = a.DB.WithContext(c.Request.Context()).Where("task_id = ?", taskID).Find(&stages).Error
	signoffDone := false
	for _, stage := range stages {
		if stage.Name == "SIGNOFF" && (stage.Status == models.StageStatusReleased || stage.Status == models.StageStatusSucceeded) {
			signoffDone = true
		}
	}

	// Real hardening evidence from the shared workspace: the GDS render (the
	// PNG the RENDER stage produced under gds/) and the merged metrics of every
	// EDA report (reports/*_report.json → "metrics"), so the signoff view can
	// show the chip image and its parameter table.
	workspace := a.Orch.TaskWorkspace(taskID)
	gdsImage := ""
	gdsFiles := []string{}
	if entries, err := os.ReadDir(filepath.Join(workspace, "gds")); err == nil {
		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			rel := "gds/" + entry.Name()
			gdsFiles = append(gdsFiles, rel)
			ext := strings.ToLower(filepath.Ext(entry.Name()))
			if gdsImage == "" && (ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".svg") {
				gdsImage = rel
			}
		}
	}
	// The RENDER stage writes its layout image to reports/gds.png (copying
	// gds/<top>.png when hardening produced one); fall back there — and to the
	// schematic render — so the signoff view shows the chip as soon as any
	// layout/netlist image exists.
	if gdsImage == "" {
		for _, candidate := range []string{"reports/gds.png", "reports/schematic.png"} {
			if _, err := os.Stat(filepath.Join(workspace, filepath.FromSlash(candidate))); err == nil {
				gdsImage = candidate
				gdsFiles = append(gdsFiles, candidate)
				break
			}
		}
	}
	metrics := map[string]any{}
	if reports, err := filepath.Glob(filepath.Join(workspace, "reports", "*_report.json")); err == nil {
		sort.Strings(reports)
		for _, report := range reports {
			data, readErr := os.ReadFile(report)
			if readErr != nil {
				continue
			}
			var parsed struct {
				Metrics map[string]any `json:"metrics"`
			}
			if json.Unmarshal(data, &parsed) == nil {
				for k, v := range parsed.Metrics {
					// keep engineering parameters, drop presentation noise
					if v == nil || k == "images" || k == "engine" || k == "rendered" {
						continue
					}
					metrics[k] = v
				}
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"stateLabel":      ternary(signoffDone, "Approved", "Awaiting final approval"),
		"message":         ternary(signoffDone, "Signoff is approved and the export bundle can be delivered.", "The task remains blocked on final signoff approval."),
		"packageContents": []string{"Final RTL snapshot and verification bundle", "EDA timing and implementation reports", "Approval trail with orchestrator review metadata"},
		"checklist":       []gin.H{{"id": "signoff-1", "label": "DRC/LVS package ready", "detail": "Mock signoff package prepared by the EDA Service.", "done": signoffDone}, {"id": "signoff-2", "label": "Power and timing guardrail accepted", "detail": "Review the latest synthesized report before release.", "done": signoffDone}, {"id": "signoff-3", "label": "Tapeout handoff approved", "detail": "Orchestrator approval is required to release EXPORT.", "done": signoffDone}},
		"gdsImage":        gdsImage,
		"gdsFiles":        gdsFiles,
		"metrics":         metrics,
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

// etaLabel is the cheap per-row label for the task LIST (no stage query).
func etaLabel(task models.Task) string {
	switch task.Status {
	case models.TaskStatusCompleted:
		return "Ready"
	case models.TaskStatusFailed:
		return "Blocked"
	default:
		return "In progress"
	}
}

// stagesEtaLabel derives a REAL ETA from the stage DAG state instead of the
// static task field (which showed "Ready" while the run was still going):
// remaining agent stages ≈ 5 min each (LLM generation), EDA stages ≈ 2 min.
func stagesEtaLabel(task models.Task, stages []models.Stage) string {
	if task.Status == models.TaskStatusCompleted {
		return "Ready"
	}
	remainingMin := 0
	failed := false
	for _, stage := range stages {
		switch stage.Status {
		case models.StageStatusSucceeded, models.StageStatusReleased:
			continue
		case models.StageStatusFailed:
			failed = true
		default:
			switch stage.Name {
			case "PLAN", "RTL_GEN", "TB_GEN", "RTL_REPAIR":
				remainingMin += 5
			case "SYNTH", "PNR":
				remainingMin += 4
			default:
				remainingMin += 2
			}
		}
	}
	if failed {
		return "Blocked — retry the failed stage"
	}
	if remainingMin == 0 {
		return "Ready"
	}
	return fmt.Sprintf("≈ %d min", remainingMin)
}

// readTaskArtifacts reads the artifact list DEDUPED by name (stage retries
// re-push their artifacts, which inflated the lineage count — 28 "linked
// outputs" for a dozen real files). The LAST record for a name wins.
func (a *App) readTaskArtifacts(ctx context.Context, taskID string) []map[string]any {
	raw := a.readJSONList(ctx, fmt.Sprintf("task:%s:artifacts", taskID))
	byKey := map[string]int{}
	out := make([]map[string]any, 0, len(raw))
	for _, art := range raw {
		name, _ := art["name"].(string)
		if name == "" {
			out = append(out, art)
			continue
		}
		if idx, seen := byKey[name]; seen {
			out[idx] = art
			continue
		}
		byKey[name] = len(out)
		out = append(out, art)
	}
	return out
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
