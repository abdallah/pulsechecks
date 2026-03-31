package provider

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type ApiClient struct {
	BaseURL    string
	Token      string
	HTTPClient *http.Client
}

type Team struct {
	TeamId    string `json:"teamId"`
	Name      string `json:"name"`
	CreatedAt string `json:"createdAt"`
}

type Check struct {
	CheckId       string `json:"checkId"`
	TeamId        string `json:"teamId"`
	Name          string `json:"name"`
	CheckType     string `json:"type"`
	Status        string `json:"status"`
	PeriodSeconds int    `json:"periodSeconds,omitempty"`
	Schedule      string `json:"schedule,omitempty"`
	GraceSeconds  int    `json:"graceSeconds"`
	Token         string `json:"token"`
	LastPingAt    string `json:"lastPingAt,omitempty"`
	NextDueAt     string `json:"nextDueAt,omitempty"`
	CreatedAt     string `json:"createdAt"`
}

func (c *ApiClient) doRequest(method, path string, body interface{}) (*http.Response, error) {
	var reqBody io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reqBody = bytes.NewBuffer(jsonBody)
	}

	req, err := http.NewRequest(method, c.BaseURL+path, reqBody)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}

	return c.HTTPClient.Do(req)
}

func (c *ApiClient) CreateTeam(name string) (*Team, error) {
	body := map[string]string{"name": name}
	resp, err := c.doRequest("POST", "/teams", body)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var team Team
	if err := json.NewDecoder(resp.Body).Decode(&team); err != nil {
		return nil, err
	}

	return &team, nil
}

func (c *ApiClient) GetTeam(teamId string) (*Team, error) {
	resp, err := c.doRequest("GET", "/teams/"+teamId, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, nil
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var team Team
	if err := json.NewDecoder(resp.Body).Decode(&team); err != nil {
		return nil, err
	}

	return &team, nil
}

type CheckRequest struct {
	Name          string `json:"name"`
	Type          string `json:"type"`
	PeriodSeconds int    `json:"periodSeconds,omitempty"`
	Schedule      string `json:"schedule,omitempty"`
	GraceSeconds  int    `json:"graceSeconds"`
}

func (c *ApiClient) CreateCheck(teamId string, req CheckRequest) (*Check, error) {
	resp, err := c.doRequest("POST", "/teams/"+teamId+"/checks", req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var check Check
	if err := json.NewDecoder(resp.Body).Decode(&check); err != nil {
		return nil, err
	}

	return &check, nil
}

func (c *ApiClient) GetCheck(teamId, checkId string) (*Check, error) {
	resp, err := c.doRequest("GET", "/teams/"+teamId+"/checks/"+checkId, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, nil
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var check Check
	if err := json.NewDecoder(resp.Body).Decode(&check); err != nil {
		return nil, err
	}

	return &check, nil
}

func (c *ApiClient) UpdateCheck(teamId, checkId string, req CheckRequest) (*Check, error) {
	resp, err := c.doRequest("PATCH", "/teams/"+teamId+"/checks/"+checkId, req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var check Check
	if err := json.NewDecoder(resp.Body).Decode(&check); err != nil {
		return nil, err
	}

	return &check, nil
}

func (c *ApiClient) DeleteCheck(teamId, checkId string) error {
	resp, err := c.doRequest("DELETE", "/teams/"+teamId+"/checks/"+checkId, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("API error: %d", resp.StatusCode)
	}

	return nil
}
