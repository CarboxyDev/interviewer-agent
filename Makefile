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
	uv run mypy src

format:
	uv run ruff check --fix .
	uv run ruff format .

serve:
	uv run voice-interviewer serve

doctor:
	uv run voice-interviewer doctor


# V2-008: isolated flow study; no runtime or provider integration.
prototype:
	uv run python prototypes/practice/server.py

prototype-test:
	uv run python -m pytest -c tests/prototype/pytest.ini tests/prototype
