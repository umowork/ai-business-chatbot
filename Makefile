# AI Business Chatbot — Makefile
# Targets: install, test, lint, run, clean, help

PROJECT_NAME := ai-business-chatbot
PYTHON := python3

.PHONY: all install test lint run run-api run-all clean help check

all: lint test

# ── Installation ────────────────────────────────────────────────────────

install:
	pip install -U pip
	pip install -r requirements.txt
	@if [ -f requirements-test.txt ]; then pip install -r requirements-test.txt; fi

install-dev:
	pip install -U pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# ── Testing ─────────────────────────────────────────────────────────────

test:
	MOCK_MODE=true python -m pytest tests/ -v --tb=short -x

test-coverage:
	MOCK_MODE=true python -m pytest tests/ -v --tb=short --cov=. --cov-report=term --cov-report=html

test-quick:
	MOCK_MODE=true python -m pytest tests/ -v --tb=short -x -q

# ── Linting ─────────────────────────────────────────────────────────────

lint:
	ruff check . --ignore E501 --exclude __pycache__,.venv

lint-fix:
	ruff check . --ignore E501 --fix --exclude __pycache__,.venv

# ── Type Checking ───────────────────────────────────────────────────────

typecheck:
	MOCK_MODE=true python -m mypy --ignore-missing-imports main.py config.py models/ services/ bot/ api/

# ── Running ─────────────────────────────────────────────────────────────

run:
	MOCK_MODE=true python main.py

run-api:
	MOCK_MODE=true python main.py --api

run-all:
	MOCK_MODE=true python main.py --all

run-prod:
	python main.py

# ── Docker ──────────────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Cleanup ─────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pkl" -delete
	rm -f bot.db

# ── Code Quality Checks ─────────────────────────────────────────────────

check:
	@echo "=== Line count ==="
	@find . -name '*.py' -not -path './.venv/*' -not -path './__pycache__/*' | xargs wc -l | tail -1
	@echo ""
	@echo "=== Mock/TODO/FIXME check (excl. tests) ==="
	@echo "Remaining mocks/todos: $$(grep -rE 'Mock|mock_|MOCK|TODO|FIXME|NotImplementedError' --include='*.py' . | grep -v test_ | grep -v __pycache__ | wc -l)"
	@echo ""
	@echo "=== Running tests ==="
	@MOCK_MODE=true python -m pytest tests/ -v --tb=short || true
	@echo ""
	@echo "=== Done ==="

# ── Help ────────────────────────────────────────────────────────────────

help:
	@echo "AI Business Chatbot — Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install       — Install production dependencies"
	@echo "  install-dev   — Install all dependencies (including dev)"
	@echo "  test          — Run test suite"
	@echo "  test-coverage — Run tests with coverage report"
	@echo "  lint          — Run ruff linter"
	@echo "  lint-fix      — Run ruff linter with auto-fix"
	@echo "  typecheck     — Run mypy type checker"
	@echo "  run           — Run Telegram bot (mock mode)"
	@echo "  run-api       — Run Web API only"
	@echo "  run-all       — Run both Telegram bot and Web API"
	@echo "  run-prod      — Run in production mode"
	@echo "  docker-build  — Build Docker image"
	@echo "  docker-up     — Start services with Docker Compose"
	@echo "  docker-down   — Stop services"
	@echo "  clean         — Clean cache files"
	@echo "  check         — Self-check (lines, mocks, tests)"
	@echo "  help          — Show this help"
