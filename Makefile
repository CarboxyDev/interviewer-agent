.PHONY: bootstrap check test lint format serve doctor prototype prototype-test

bootstrap:
	uv sync --all-groups
	uv run playwright install chromium

check: lint test

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src benchmarks prototypes/practice/server.py web/serve.py

format:
	uv run ruff check --fix .
	uv run ruff format .

serve:
	uv run voice-interviewer serve

doctor:
	uv run voice-interviewer doctor


# V2-010: production web bundle with synthetic sessions; no provider integration.
.PHONY: web web-check web-test
web:
	npm --prefix web run build
	uv run python web/serve.py

web-check:
	npm --prefix web run check

web-test:
	npm --prefix web run build
	uv run python -m pytest -c tests/web/pytest.ini tests/web

# Preserve existing local commands while moving the maintained UI into web/.
prototype: web
prototype-test: web-test
