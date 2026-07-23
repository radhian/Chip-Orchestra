SHELL := /bin/bash

CORE_DIR := $(CURDIR)/core
EDA_DIR := $(CURDIR)/eda

.PHONY: core-up core-down eda-up eda-down logs

core-up:
	cd $(CORE_DIR) && cp -n .env.example .env || true && docker compose up -d --build

core-down:
	cd $(CORE_DIR) && docker compose down

eda-up:
	cd $(EDA_DIR) && cp -n .env.example .env || true && docker compose up -d --build

eda-down:
	cd $(EDA_DIR) && docker compose down

logs:
	cd $(CORE_DIR) && docker compose logs -f orchestrator-service agent-service
