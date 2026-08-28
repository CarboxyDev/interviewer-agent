.PHONY: bootstrap check test lint format serve doctor

bootstrap:
	uv sync --all-groups
	uv run playwright install chromium

check: lint test

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

format:
	uv run ruff check --fix .
	uv run ruff format .

serve:
	uv run voice-interviewer serve

doctor:
	uv run voice-interviewer doctor

