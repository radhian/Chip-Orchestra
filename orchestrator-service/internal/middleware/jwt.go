package middleware

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"strings"
	"time"

	"chip-orchestra/orchestrator-service/internal/models"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

type JWTClaims struct {
	UserID   string   `json:"user_id"`
	Username string   `json:"username"`
	FullName string   `json:"full_name"`
	Roles    []string `json:"roles"`
	jwt.RegisteredClaims
}

func HashPassword(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

func IssueToken(user models.User, secret string, ttl time.Duration) (string, error) {
	claims := JWTClaims{
		UserID:   user.ID,
		Username: user.Username,
		FullName: user.FullName,
		Roles:    splitRoles(user.Roles),
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(ttl)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			Subject:   user.ID,
		},
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(secret))
}

func JWTAuth(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Browser-native flows (<img src>, direct download links) cannot set an
		// Authorization header, so a `?token=<jwt>` query parameter is accepted
		// as a fallback.
		raw := ""
		authHeader := c.GetHeader("Authorization")
		if authHeader != "" {
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid authorization header"})
				return
			}
			raw = parts[1]
		} else if q := c.Query("token"); q != "" {
			raw = q
		} else {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization header"})
			return
		}

		token, err := jwt.ParseWithClaims(raw, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
			return []byte(secret), nil
		})
		if err != nil || !token.Valid {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}

		claims, ok := token.Claims.(*JWTClaims)
		if !ok {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token claims"})
			return
		}

		c.Set("principal", claims)
		c.Next()
	}
}

func splitRoles(raw string) []string {
	parts := strings.Split(raw, ",")
	roles := make([]string, 0, len(parts))
	for _, part := range parts {
		trimmed := strings.TrimSpace(part)
		if trimmed != "" {
			roles = append(roles, trimmed)
		}
	}
	if len(roles) == 0 {
		return []string{string(models.UserRoleDesigner)}
	}
	return roles
}
