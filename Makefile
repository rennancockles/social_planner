.PHONY: help dev backend frontend install install-backend install-frontend lint lint-fix fmt type-check test

.DEFAULT_GOAL := help

-include .env
export

PROJECT_NAME=Social Planner
PKG_MANAGER=uv
BACKEND_PORT ?= 8000

BOLD := \033[1m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

help: ## Show this help message
	@echo "$(BOLD)$(PROJECT_NAME) Development Commands$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(BLUE)%-20s$(RESET) %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install Python backend dependencies
	@echo "$(YELLOW)Installing backend dependencies...$(RESET)"
	@$(PKG_MANAGER) sync
	@echo "$(GREEN)✓ Backend dependencies installed$(RESET)"

install-frontend: ## Install frontend dependencies
	@echo "$(YELLOW)Installing frontend dependencies...$(RESET)"
	@cd frontend && npm install
	@echo "$(GREEN)✓ Frontend dependencies installed$(RESET)"

dev: ## Start backend and frontend (BACKEND_PORT=8000 by default)
	@echo "$(YELLOW)Starting backend on :$(BACKEND_PORT) and frontend on :5173...$(RESET)"
	@$(PKG_MANAGER) run uvicorn app.main:app --reload --port $(BACKEND_PORT) & \
	BACKEND_PID=$$!; \
	trap "kill $$BACKEND_PID 2>/dev/null" EXIT INT TERM; \
	cd frontend && npm run dev; \
	wait

backend: ## Start backend only (BACKEND_PORT=8000 by default)
	@$(PKG_MANAGER) run uvicorn app.main:app --reload --port $(BACKEND_PORT)

frontend: ## Start frontend only (port 5173)
	@cd frontend && npm run dev

# Development and Quality Commands
# Note: The order of lint operations matches pre-commit hooks for consistency:
lint-fix: fmt ruff-fix ruff-check format-check type-check ## Run all linting and formatting checks
lint: ruff-check format-check type-check ## Run all linting and formatting checks
ruff: ruff-check format-check ## Run Ruff linting and formatting checks
type-check: mypy ty ## Run MyPy and Ty type checks

ruff-check: ## Run Ruff linting
	@echo "$(YELLOW)Running Ruff linting...$(RESET)"
	@$(PKG_MANAGER) run ruff check .

format-check: ## Check code formatting without making changes
	@echo "$(YELLOW)Checking code formatting...$(RESET)"
	@$(PKG_MANAGER) run ruff format . --check

ruff-fix: ## Run Ruff linting with auto-fix (matches pre-commit behavior)
	@echo "$(YELLOW)Running Ruff linting with auto-fix...$(RESET)"
	@$(PKG_MANAGER) run ruff check . --fix || true

fmt: ## Run code formatting
	@echo "$(YELLOW)Running code formatting...$(RESET)"
	@$(PKG_MANAGER) run ruff format .

pre-commit-sim: ## Simulate pre-commit hooks exactly (for troubleshooting)
	@echo "$(YELLOW)Simulating pre-commit hooks...$(RESET)"
	@$(PKG_MANAGER) run ruff check . --fix --exit-non-zero-on-fix || echo "Ruff applied fixes"
	@$(PKG_MANAGER) run ruff format .

mypy: ## Run MyPy type checking
	@echo "$(YELLOW)Running MyPy type checking...$(RESET)"
	@$(PKG_MANAGER) run mypy

ty: ## Run Ty type checking
	@echo "$(YELLOW)Running Ty check...$(RESET)"
	@$(PKG_MANAGER) run ty check

test: ## Run all tests with coverage (parallel via pytest-xdist)
	@echo "$(YELLOW)Running all tests with coverage...$(RESET)"
	@$(PKG_MANAGER) run pytest $(PYTEST_PARALLEL) --cov --cov-report=term-missing:skip-covered --cov-report=html

test-unit: ## Run all unit tests with coverage (parallel via pytest-xdist)
	@echo "$(YELLOW)Running unit tests with coverage...$(RESET)"
	@$(PKG_MANAGER) run pytest $(PYTEST_PARALLEL) --cov --cov-report=term-missing:skip-covered --cov-report=html -m "unit"


# Environment management
env-check: ## Check environment setup
	@echo "$(YELLOW)Checking environment setup...$(RESET)"
	@echo "$(BLUE)Python version:$(RESET) $$(python --version 2>/dev/null || echo 'Not found')"
	@echo "$(BLUE)$(PKG_MANAGER) version:$(RESET) $$($(PKG_MANAGER) --version 2>/dev/null || echo 'Not found')"
	@echo "$(BLUE)Pre-commit installed:$(RESET) $$($(PKG_MANAGER) run pre-commit --version 2>/dev/null || echo 'Not found')"
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ .env file exists$(RESET)"; \
	else \
		echo "$(YELLOW)⚠ .env file not found - copy from .env.example$(RESET)"; \
	fi
