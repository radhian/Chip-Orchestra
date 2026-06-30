package eda

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

type CreateJobRequest struct {
	TaskID    string            `json:"task_id"`
	Stage     string            `json:"stage"`
	Spec      string            `json:"spec"`
	Metadata  map[string]any    `json:"metadata,omitempty"`
	Artifacts map[string]string `json:"artifacts,omitempty"`
}

type CreateJobResponse struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type JobStatusResponse struct {
	JobID     string         `json:"job_id"`
	Status    string         `json:"status"`
	Stage     string         `json:"stage"`
	Progress  int            `json:"progress"`
	Report    map[string]any `json:"report,omitempty"`
	Error     string         `json:"error,omitempty"`
	UpdatedAt string         `json:"updated_at"`
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 60 * time.Second},
	}
}

func (c *Client) CreateJob(ctx context.Context, req CreateJobRequest) (*CreateJobResponse, error) {
	payload, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, fmt.Sprintf("%s/eda/jobs", c.baseURL), bytes.NewReader(payload))
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
		return nil, fmt.Errorf("eda service returned status %d", resp.StatusCode)
	}

	var out CreateJobResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) GetJobStatus(ctx context.Context, jobID string) (*JobStatusResponse, error) {
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf("%s/eda/jobs/%s/status", c.baseURL, jobID), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= http.StatusBadRequest {
		return nil, fmt.Errorf("eda service returned status %d", resp.StatusCode)
	}

	var out JobStatusResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return &out, nil
}
