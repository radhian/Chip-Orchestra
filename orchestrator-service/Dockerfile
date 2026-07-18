FROM golang:1.23-alpine AS builder
ENV GOPROXY=https://goproxy.cn,direct
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod tidy
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /orchestrator ./cmd/orchestrator

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /orchestrator /usr/local/bin/orchestrator
EXPOSE 8080
CMD ["/usr/local/bin/orchestrator"]
