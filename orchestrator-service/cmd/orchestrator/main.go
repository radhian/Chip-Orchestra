package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"chip-orchestra/orchestrator-service/internal/api"
	"chip-orchestra/orchestrator-service/internal/dispatcher"
	edaclient "chip-orchestra/orchestrator-service/internal/eda"
	"chip-orchestra/orchestrator-service/internal/middleware"
	"chip-orchestra/orchestrator-service/internal/models"
	"chip-orchestra/orchestrator-service/internal/orchestrator"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

func main() {
	ctx := context.Background()
	dsn := getenv("MYSQL_DSN", "chip:chip@tcp(mysql:3306)/chip_orchestra?charset=utf8mb4&parseTime=True&loc=UTC")
	jwtSecret := getenv("JWT_SECRET", "chip-orchestra-secret")
	redisAddr := getenv("REDIS_ADDR", "redis:6379")
	agentURL := getenv("AGENT_SERVICE_URL", "http://agent-service:8001")
	edaURL := getenv("EDA_SERVICE_URL", "http://eda-service:8002")
	port := getenv("PORT", "8080")
	seedUsername := getenv("DEFAULT_USERNAME", "admin")
	seedFullName := getenv("DEFAULT_FULL_NAME", "Admin")
	seedEmail := getenv("DEFAULT_EMAIL", "admin@chip-orchestra.local")
	seedPassword := getenv("DEFAULT_PASSWORD", "chip-orchestra")

	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("failed to connect mysql: %v", err)
	}
	if err := db.AutoMigrate(&models.User{}, &models.Task{}, &models.Stage{}, &models.StageAttempt{}); err != nil {
		log.Fatalf("failed to migrate schema: %v", err)
	}

	redisClient := redis.NewClient(&redis.Options{Addr: redisAddr})
	if err := redisClient.Ping(ctx).Err(); err != nil {
		log.Fatalf("failed to connect redis: %v", err)
	}

	if err := seedDefaultUser(ctx, db, seedUsername, seedFullName, seedEmail, seedPassword); err != nil {
		log.Fatalf("failed to seed user: %v", err)
	}

	if strings.EqualFold(getenv("MIGRATE_ONLY", "false"), "true") {
		log.Println("schema migration completed; exiting due to MIGRATE_ONLY=true")
		return
	}

	agentClient := dispatcher.NewClient(agentURL)
	edaClient := edaclient.NewClient(edaURL)
	orch := orchestrator.NewService(db, redisClient, agentClient, edaClient)
	go orch.ScheduleLoop(context.Background(), 3*time.Second)

	app := &api.App{DB: db, Redis: redisClient, Orch: orch, Agent: agentClient, JWTSecret: jwtSecret, Password: seedPassword}
	router := gin.Default()
	router.Use(corsMiddleware())
	app.RegisterRoutes(router)

	log.Printf("Orchestrator Service listening on :%s", port)
	if err := router.Run(fmt.Sprintf(":%s", port)); err != nil {
		log.Fatalf("server stopped: %v", err)
	}
}

func seedDefaultUser(ctx context.Context, db *gorm.DB, username, fullName, email, password string) error {
	var user models.User
	adminRole := string(models.UserRoleAdmin)
	err := db.WithContext(ctx).
		Where("username = ? OR roles = ? OR roles LIKE ? OR roles LIKE ? OR roles LIKE ?", username, adminRole, adminRole+",%", "%,"+adminRole+",%", "%,"+adminRole).
		First(&user).Error
	if err == nil {
		return nil
	}
	if err != gorm.ErrRecordNotFound {
		return err
	}
	user = models.User{ID: uuid.NewString(), Username: username, FullName: fullName, Email: email, PasswordHash: middleware.HashPassword(password), Roles: adminRole}
	return db.WithContext(ctx).Create(&user).Error
}

func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
