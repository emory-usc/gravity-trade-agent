.PHONY: install dev test analyze backtest clean

install:
	uv sync

dev:
	uv sync --extra dev --extra llm

test:
	uv run pytest

analyze:
	uv run gravity analyze NVDA

backtest:
	uv run gravity backtest

clean:
	rm -rf .venv .pytest_cache .coverage htmlcov build dist *.egg-info
