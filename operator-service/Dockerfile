FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod tidy
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /operator ./cmd/operator

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /operator /usr/local/bin/operator
EXPOSE 8080
CMD ["/usr/local/bin/operator"]
