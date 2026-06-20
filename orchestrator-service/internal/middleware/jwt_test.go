package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"chip-orchestra/orchestrator-service/internal/models"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestJWTAuthRejectsMissingAuthorizationHeader(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(JWTAuth("secret"))
	router.GET("/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.Contains(t, rec.Body.String(), "missing authorization header")
}

func TestJWTAuthRejectsMalformedAuthorizationHeader(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(JWTAuth("secret"))
	router.GET("/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Token abc")
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.Contains(t, rec.Body.String(), "invalid authorization header")
}

func TestJWTAuthRejectsExpiredToken(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(JWTAuth("secret"))
	router.GET("/protected", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	token, err := IssueToken(models.User{ID: "user-1", Username: "tester", FullName: "Token Tester", Roles: string(models.UserRoleAdmin)}, "secret", -time.Minute)
	require.NoError(t, err)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusUnauthorized, rec.Code)
	assert.Contains(t, rec.Body.String(), "invalid token")
}

func TestJWTAuthSetsPrincipalForValidToken(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(JWTAuth("secret"))
	router.GET("/protected", func(c *gin.Context) {
		principal := c.MustGet("principal").(*JWTClaims)
		c.JSON(http.StatusOK, gin.H{
			"user_id":   principal.UserID,
			"username":  principal.Username,
			"full_name": principal.FullName,
			"roles":     principal.Roles,
		})
	})

	token, err := IssueToken(models.User{ID: "user-1", Username: "tester", FullName: "Token Tester", Roles: "ADMIN,DESIGNER"}, "secret", time.Hour)
	require.NoError(t, err)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	router.ServeHTTP(rec, req)

	require.Equal(t, http.StatusOK, rec.Code)

	var body map[string]any
	require.NoError(t, json.Unmarshal(rec.Body.Bytes(), &body))
	assert.Equal(t, "user-1", body["user_id"])
	assert.Equal(t, "tester", body["username"])
	assert.Equal(t, "Token Tester", body["full_name"])
	assert.ElementsMatch(t, []any{"ADMIN", "DESIGNER"}, body["roles"].([]any))
}
