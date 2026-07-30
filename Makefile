PYTHON ?= python3.12
UV ?= uv

.PHONY: install lint format-check typecheck test test-integration docs build docker-build \
	dev-up dev-down migrate seed demo web-install web-test web-build verify \
	web-audit web-lint web-format-check

install:
	$(UV) sync --all-extras --frozen

lint:
	$(UV) run ruff check .

format-check:
	$(UV) run ruff format --check .

typecheck:
	$(UV) run mypy apps packages

test:
	$(UV) run pytest -m "not integration and not performance and not live_provider"

test-integration:
	$(UV) run pytest -m integration

docs:
	$(UV) run mkdocs build --strict

build:
	$(UV) run python -m build

docker-build:
	docker compose build migrate web

web-install:
	npm ci

web-test:
	npm test

web-audit:
	npm run audit

web-lint:
	npm run lint

web-format-check:
	npm run format:check

web-build:
	npm run typecheck
	npm run build

dev-up:
	docker compose up --build -d

dev-down:
	docker compose down

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m eval_platform_api.seed

demo:
	docker compose up --build -d
	docker compose run --rm api alembic upgrade head
	docker compose run --rm api python -m eval_platform_api.seed
	docker compose run --rm api python -m eval_platform_api.demo

verify: lint format-check typecheck test docs build web-audit web-format-check \
	web-lint web-test web-build
