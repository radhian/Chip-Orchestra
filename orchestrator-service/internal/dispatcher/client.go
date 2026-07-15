package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

type InvokeRequest struct {
	TaskID       string            `json:"task_id"`
	Stage        string            `json:"stage"`
	Prompt       string            `json:"prompt"`
	Tools        []string          `json:"tools"`
	Context      map[string]any    `json:"context"`
	Artifacts    map[string]string `json:"artifacts,omitempty"`
	Instructions map[string]any    `json:"instructions,omitempty"`
	// Optional workspace-aware fields (additive, omitted when empty).
	WorkspaceRoot     string   `json:"workspace_root,omitempty"`
	ArtifactInventory []string `json:"artifact_inventory,omitempty"`
	EDAReports        []string `json:"eda_reports,omitempty"`
	ReferenceFiles    []string `json:"reference_files,omitempty"`
}

type InvokeResponse struct {
	Status          string            `json:"status"`
	Summary         string            `json:"summary"`
	Diagnostics     []map[string]any  `json:"diagnostics"`
	Artifacts       []map[string]any  `json:"artifacts"`
	WorkspaceFiles  map[string]string `json:"workspace_files"`
	RecommendedNext string            `json:"recommended_next"`
	// New optional structured fields (ignored if the agent omits them).
	StructuredConclusion map[string]any `json:"structured_conclusion,omitempty"`
	ArtifactRefs         []string       `json:"artifact_refs,omitempty"`
}

func NewClient(baseURL string) *Client {
	// /agent/invoke is synchronous and runs LLM generation + repair loops, so
	// the request can legitimately take many minutes on large design briefs.
	timeout := 1800 * time.Second
	if v := os.Getenv("AGENT_INVOKE_TIMEOUT_SECONDS"); v != "" {
		if secs, err := strconv.Atoi(v); err == nil && secs > 0 {
			timeout = time.Duration(secs) * time.Second
		}
	}
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: timeout},
	}
}

// Models proxies the agent service's model listing (e.g. installed Ollama
// models) so the frontend can offer a per-task LLM picker.
func (c *Client) Models(ctx context.Context) (map[string]any, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf("%s/agent/models", c.baseURL), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= http.StatusBadRequest {
		return nil, fmt.Errorf("agent service returned status %d", resp.StatusCode)
	}
	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) Invoke(ctx context.Context, req InvokeRequest) (*InvokeResponse, error) {
	payload, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, fmt.Sprintf("%s/agent/invoke", c.baseURL), bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= http.StatusBadRequest {
		return nil, fmt.Errorf("agent service returned status %d", resp.StatusCode)
	}

	var out InvokeResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}
