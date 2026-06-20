package models

import "time"

type TaskStatus string

type StageStatus string

type LaunchMode string

type UserRole string

const (
	TaskStatusPending   TaskStatus = "PENDING"
	TaskStatusRunning   TaskStatus = "RUNNING"
	TaskStatusFailed    TaskStatus = "FAILED"
	TaskStatusCompleted TaskStatus = "COMPLETED"
	TaskStatusBlocked   TaskStatus = "BLOCKED"
	TaskStatusCancelled TaskStatus = "CANCELLED"
)

const (
	StageStatusNotStarted       StageStatus = "NOT_STARTED"
	StageStatusQueued           StageStatus = "QUEUED"
	StageStatusDispatching      StageStatus = "DISPATCHING"
	StageStatusRunning          StageStatus = "RUNNING"
	StageStatusSucceeded        StageStatus = "SUCCEEDED"
	StageStatusFailed           StageStatus = "FAILED"
	StageStatusRetryWait        StageStatus = "RETRY_WAIT"
	StageStatusBlocked          StageStatus = "BLOCKED"
	StageStatusAwaitingApproval StageStatus = "AWAITING_APPROVAL"
	StageStatusReleased         StageStatus = "RELEASED"
	StageStatusCancelled        StageStatus = "CANCELLED"
)

const (
	LaunchModeFullFlowGated LaunchMode = "FULL_FLOW_GATED"
	LaunchModeGenOnly       LaunchMode = "GEN_ONLY"
	LaunchModeVerifyRescue  LaunchMode = "VERIFY_RESCUE"
	LaunchModeSynthOnly     LaunchMode = "SYNTH_ONLY"
)

const (
	UserRoleAdmin        UserRole = "ADMIN"
	UserRoleDesigner     UserRole = "DESIGNER"
	UserRoleVerification UserRole = "VERIFICATION"
	UserRoleViewer       UserRole = "VIEWER"
)

type User struct {
	ID           string    `gorm:"type:char(36);primaryKey" json:"id"`
	Username     string    `gorm:"size:128;uniqueIndex;not null" json:"username"`
	Email        string    `gorm:"size:255;uniqueIndex;not null" json:"email"`
	FullName     string    `gorm:"size:255;not null" json:"full_name"`
	PasswordHash string    `gorm:"size:128;not null" json:"-"`
	Roles        string    `gorm:"type:text;not null;default:'DESIGNER'" json:"roles"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type Task struct {
	ID           string     `gorm:"type:char(36);primaryKey" json:"task_id"`
	Name         string     `gorm:"size:255;not null" json:"name"`
	Slug         string     `gorm:"size:255;uniqueIndex;not null" json:"slug"`
	Description  string     `gorm:"type:text" json:"description"`
	DesignBrief  string     `gorm:"type:longtext" json:"design_brief"`
	LaunchMode   LaunchMode `gorm:"size:64;not null" json:"launch_mode"`
	RepoMode     string     `gorm:"size:64;not null" json:"repo_mode"`
	RepoSource   string     `gorm:"size:512" json:"repo_source"`
	RepoBranch   string     `gorm:"size:255" json:"repo_branch"`
	TemplateID   string     `gorm:"size:255" json:"template_id"`
	PDKID        string     `gorm:"size:128" json:"pdk_id"`
	StdcellLibID string     `gorm:"size:128" json:"stdcell_lib_id"`
	ReviewGates  string     `gorm:"type:text" json:"review_gates"`
	OwnerID      string     `gorm:"type:char(36);index" json:"owner_id"`
	OwnerName    string     `gorm:"size:255" json:"owner_name"`
	Status       TaskStatus `gorm:"size:64;index;not null" json:"status"`
	CurrentStage string     `gorm:"size:128;index" json:"current_stage"`
	LastError    string     `gorm:"type:text" json:"last_error,omitempty"`
	EtaSeconds   int        `json:"eta_seconds"`
	AttemptCount int        `gorm:"not null;default:1" json:"attempt_count"`
	CreatedAt    time.Time  `json:"created_at"`
	UpdatedAt    time.Time  `json:"updated_at"`
	Stages       []Stage    `gorm:"foreignKey:TaskID" json:"stages,omitempty"`
}

type Stage struct {
	ID            string      `gorm:"type:char(36);primaryKey" json:"stage_id"`
	TaskID        string      `gorm:"type:char(36);index;not null" json:"task_id"`
	Name          string      `gorm:"size:128;index:idx_task_stage_name,unique;not null" json:"name"`
	Status        StageStatus `gorm:"size:64;index;not null" json:"status"`
	DependsOn     string      `gorm:"type:text" json:"depends_on"`
	SortOrder     int         `gorm:"not null" json:"sort_order"`
	Progress      int         `gorm:"not null;default:0" json:"progress"`
	RetryCount    int         `gorm:"not null;default:0" json:"retry_count"`
	AttemptNumber int         `gorm:"not null;default:0" json:"attempt_number"`
	ExternalJobID string      `gorm:"size:128" json:"external_job_id,omitempty"`
	LastError     string      `gorm:"type:text" json:"last_error,omitempty"`
	StartedAt     *time.Time  `json:"started_at,omitempty"`
	CompletedAt   *time.Time  `json:"completed_at,omitempty"`
	CreatedAt     time.Time   `json:"created_at"`
	UpdatedAt     time.Time   `json:"updated_at"`
}

type StageAttempt struct {
	ID            string      `gorm:"type:char(36);primaryKey" json:"id"`
	TaskID        string      `gorm:"type:char(36);index;not null" json:"task_id"`
	StageID       string      `gorm:"type:char(36);index;not null" json:"stage_id"`
	StageName     string      `gorm:"size:128;index;not null" json:"stage_name"`
	Attempt       int         `gorm:"not null" json:"attempt"`
	Service       string      `gorm:"size:64;not null" json:"service"`
	Status        StageStatus `gorm:"size:64;index;not null" json:"status"`
	Prompt        string      `gorm:"type:longtext" json:"prompt,omitempty"`
	Result        string      `gorm:"type:longtext" json:"result,omitempty"`
	ErrorMessage  string      `gorm:"type:text" json:"error_message,omitempty"`
	ExternalJobID string      `gorm:"size:128" json:"external_job_id,omitempty"`
	StartedAt     *time.Time  `json:"started_at,omitempty"`
	CompletedAt   *time.Time  `json:"completed_at,omitempty"`
	CreatedAt     time.Time   `json:"created_at"`
	UpdatedAt     time.Time   `json:"updated_at"`
}
