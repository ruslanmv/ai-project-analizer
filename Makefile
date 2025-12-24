.PHONY: help install dev clean test lint format audit start docker-build docker-run docs

.DEFAULT_GOAL := help

# ANSI color codes
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## 📚 Display this help message
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║        🚀 AI Project Analyzer - Development Commands          ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

install: ## 📦 Install production dependencies using UV
	@echo "$(BLUE)Installing production dependencies with UV...$(NC)"
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)UV not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)"; exit 1; }
	uv sync --no-dev
	@echo "$(GREEN)✓ Production dependencies installed$(NC)"

dev: ## 🛠️  Install all dependencies (including dev) using UV
	@echo "$(BLUE)Installing all dependencies with UV...$(NC)"
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)UV not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)"; exit 1; }
	uv sync
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

clean: ## 🧹 Remove build artifacts, cache, and temporary files
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .pytest_cache/ .ruff_cache/ .mypy_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.orig" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

test: ## 🧪 Run test suite with coverage
	@echo "$(BLUE)Running tests with pytest...$(NC)"
	uv run pytest tests/ -v --cov --cov-report=term-missing
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-fast: ## ⚡ Run tests without coverage (fast)
	@echo "$(BLUE)Running fast tests...$(NC)"
	uv run pytest tests/ -v
	@echo "$(GREEN)✓ Fast tests completed$(NC)"

lint: ## 🔍 Run ruff linter
	@echo "$(BLUE)Running ruff linter...$(NC)"
	uv run ruff check src/ tests/
	@echo "$(GREEN)✓ Linting complete$(NC)"

format: ## ✨ Format code with ruff
	@echo "$(BLUE)Formatting code with ruff...$(NC)"
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check: ## 🔬 Run mypy type checker
	@echo "$(BLUE)Running mypy type checker...$(NC)"
	uv run mypy src/
	@echo "$(GREEN)✓ Type checking complete$(NC)"

audit: ## 🛡️  Run full audit (lint, type-check, security scan)
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║              Running Full Security Audit...                    ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)[1/4] Ruff linting...$(NC)"
	@uv run ruff check src/ tests/ || exit 1
	@echo "$(GREEN)✓ Ruff check passed$(NC)"
	@echo ""
	@echo "$(YELLOW)[2/4] Type checking with mypy...$(NC)"
	@uv run mypy src/ || exit 1
	@echo "$(GREEN)✓ Type check passed$(NC)"
	@echo ""
	@echo "$(YELLOW)[3/4] Security scan with bandit...$(NC)"
	@uv run bandit -r src/ -ll || exit 1
	@echo "$(GREEN)✓ Security scan passed$(NC)"
	@echo ""
	@echo "$(YELLOW)[4/4] Running tests...$(NC)"
	@uv run pytest tests/ -v --cov || exit 1
	@echo "$(GREEN)✓ All tests passed$(NC)"
	@echo ""
	@echo "$(GREEN)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║                  ✓ Audit Complete                              ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════════════════════════════╝$(NC)"

start: ## 🚀 Start the web application
	@echo "$(BLUE)Starting AI Project Analyzer web server...$(NC)"
	uv run uvicorn ai_project_analyzer.web.app:app --reload --host 0.0.0.0 --port 8000

start-cli: ## 💻 Start CLI interface
	@echo "$(BLUE)Starting CLI...$(NC)"
	uv run ai-analyzer --help

docker-build: ## 🐳 Build Docker image
	@echo "$(BLUE)Building Docker image...$(NC)"
	docker build -t ai-project-analyzer:latest .
	@echo "$(GREEN)✓ Docker image built$(NC)"

docker-run: ## 🐳 Run Docker container
	@echo "$(BLUE)Running Docker container...$(NC)"
	docker run -p 8000:8000 --env-file .env ai-project-analyzer:latest

docker-compose-up: ## 🐳 Start with docker-compose (includes Ollama)
	@echo "$(BLUE)Starting services with docker-compose...$(NC)"
	docker compose up --build

docker-compose-down: ## 🐳 Stop docker-compose services
	docker compose down

benchmark: ## 📊 Run performance benchmarks
	@echo "$(BLUE)Running benchmarks...$(NC)"
	uv run pytest tests/ -v -m benchmark

pre-commit: ## 🎯 Run pre-commit checks
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	uv run pre-commit run --all-files

setup-hooks: ## ⚙️  Setup git pre-commit hooks
	@echo "$(BLUE)Setting up git hooks...$(NC)"
	uv run pre-commit install
	@echo "$(GREEN)✓ Git hooks installed$(NC)"

docs-serve: ## 📖 Serve documentation locally
	@echo "$(BLUE)Serving documentation...$(NC)"
	@echo "$(YELLOW)Documentation available at: http://localhost:8000$(NC)"

version: ## 🏷️  Show current version
	@echo "$(BLUE)AI Project Analyzer$(NC)"
	@grep '^version' pyproject.toml | cut -d '"' -f 2

upgrade-deps: ## ⬆️  Upgrade all dependencies
	@echo "$(BLUE)Upgrading dependencies...$(NC)"
	uv lock --upgrade
	@echo "$(GREEN)✓ Dependencies upgraded$(NC)"

check-security: ## 🔐 Run security vulnerability check
	@echo "$(BLUE)Checking for security vulnerabilities...$(NC)"
	uv run safety check --json

build: ## 📦 Build distribution packages
	@echo "$(BLUE)Building distribution packages...$(NC)"
	uv build
	@echo "$(GREEN)✓ Build complete - check dist/ directory$(NC)"

publish: ## 📤 Publish to PyPI (requires authentication)
	@echo "$(YELLOW)Publishing to PyPI...$(NC)"
	uv publish

ci: audit test ## 🔄 Run CI pipeline locally (audit + test)
	@echo "$(GREEN)╔════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║              ✓ CI Pipeline Passed                             ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════════════════════════════╝$(NC)"
