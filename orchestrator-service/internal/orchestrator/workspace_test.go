package orchestrator

import (
	"testing"

	"chip-orchestra/orchestrator-service/internal/models"

	"github.com/stretchr/testify/assert"
)

func TestWorkspaceRootFromEnvDefault(t *testing.T) {
	t.Setenv("WORKSPACE_ROOT", "")
	assert.Equal(t, defaultWorkspaceRoot, workspaceRootFromEnv())
}

func TestWorkspaceRootFromEnvOverride(t *testing.T) {
	t.Setenv("WORKSPACE_ROOT", "/data/ws")
	assert.Equal(t, "/data/ws", workspaceRootFromEnv())
}

func TestEDAReportPathsCoversAllEDAStages(t *testing.T) {
	s := NewService(nil, nil, nil, nil)
	paths := s.edaReportPaths()
	assert.Contains(t, paths, "reports/sim_report.json")
	assert.Contains(t, paths, "reports/lint_report.json")
	assert.Contains(t, paths, "reports/synth_report.json")
	assert.Contains(t, paths, "reports/pnr_report.json")
	assert.Contains(t, paths, "reports/drc_lvs_report.json")
	assert.NotContains(t, paths, "reports/spec_ingest_report.json")
}

func TestBuildInvokeRequestWiresWorkspaceAndReports(t *testing.T) {
	t.Setenv("WORKSPACE_ROOT", "/data/ws")
	s := NewService(nil, nil, nil, nil)
	task := models.Task{ID: "task-1", Name: "reg32", DesignBrief: "A register", PDKID: "sky130"}

	// Agent-only stage: no EDA reports, but workspace wired.
	rtlReq := s.buildInvokeRequest("task-1", task, "RTL_GEN", "prompt")
	assert.Equal(t, "/data/ws/task-1", rtlReq.WorkspaceRoot)
	assert.Equal(t, "/data/ws/task-1", rtlReq.Context["workspace_root"])
	assert.Equal(t, "A register", rtlReq.Context["design_brief"])
	assert.Empty(t, rtlReq.EDAReports)

	// Signoff stage receives the EDA report inventory.
	signoffReq := s.buildInvokeRequest("task-1", task, "SIGNOFF", "prompt")
	assert.NotEmpty(t, signoffReq.EDAReports)
	assert.Contains(t, signoffReq.EDAReports, "reports/drc_lvs_report.json")
}
