package dispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
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
}

type InvokeResponse struct {
	Status          string            `json:"status"`
	Summary         string            `json:"summary"`
	Diagnostics     []map[string]any  `json:"diagnostics"`
	Artifacts       []map[string]any  `json:"artifacts"`
	WorkspaceFiles  map[string]string `json:"workspace_files"`
	RecommendedNext string            `json:"recommended_next"`
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 60 * time.Second},
	}
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
