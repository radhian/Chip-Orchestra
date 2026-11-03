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
	startupRetryDeadline := time.Now().Add(getenvDuration("STARTUP_RETRY_TIMEOUT", 2*time.Minute))

	db, err := waitForMySQL(dsn, startupRetryDeadline)
	if err != nil {
		log.Fatalf("failed to connect mysql: %v", err)
	}
	if err := db.AutoMigrate(&models.User{}, &models.Task{}, &models.Stage{}, &models.StageAttempt{}); err != nil {
		log.Fatalf("failed to migrate schema: %v", err)
	}

	redisClient, err := waitForRedis(ctx, redisAddr, startupRetryDeadline)
	if err != nil {
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

func waitForMySQL(dsn string, deadline time.Time) (*gorm.DB, error) {
	var lastErr error
	for attempt := 1; ; attempt++ {
		db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
		if err == nil {
			sqlDB, sqlErr := db.DB()
			if sqlErr == nil {
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
				pingErr := sqlDB.PingContext(ctx)
				cancel()
				if pingErr == nil {
					return db, nil
				}
				lastErr = pingErr
			} else {
				lastErr = sqlErr
			}
		} else {
			lastErr = err
		}
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("mysql not ready after retries: %w", lastErr)
		}
		log.Printf("mysql not ready yet (attempt %d): %v", attempt, lastErr)
		time.Sleep(2 * time.Second)
	}
}

func waitForRedis(ctx context.Context, addr string, deadline time.Time) (*redis.Client, error) {
	var lastErr error
	for attempt := 1; ; attempt++ {
		client := redis.NewClient(&redis.Options{Addr: addr})
		if err := client.Ping(ctx).Err(); err == nil {
			return client, nil
		} else {
			lastErr = err
			_ = client.Close()
		}
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("redis not ready after retries: %w", lastErr)
		}
		log.Printf("redis not ready yet (attempt %d): %v", attempt, lastErr)
		time.Sleep(2 * time.Second)
	}
}

func seedDefaultUser(ctx context.Context, db *gorm.DB, username, fullName, email, password string) error {
	var user models.User
	err := db.WithContext(ctx).Where("username = ?", username).First(&user).Error
	if err == nil {
		return nil
	}
	if err != gorm.ErrRecordNotFound {
		return err
	}
	user = models.User{ID: uuid.NewString(), Username: username, FullName: fullName, Email: email, PasswordHash: middleware.HashPassword(password), Roles: string(models.UserRoleAdmin)}
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

func getenvDuration(key string, fallback time.Duration) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	duration, err := time.ParseDuration(value)
	if err != nil {
		log.Printf("invalid %s=%q, using default %s", key, value, fallback)
		return fallback
	}
	return duration
}
