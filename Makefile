UV ?= uv
PYTHON ?= $(UV) run python
COV_FAIL_UNDER ?= 100

.DEFAULT_GOAL := help

.PHONY: help version install format lint lint-imports test check validate score-repo smoke-endpoint hello

help:
	@printf '%s\n' \
		'Available targets:' \
		'  make version       Print the project version' \
		'  make install       Sync the uv environment with dev dependencies' \
		'  make format        Run ruff format on source, tests, and scripts' \
		'  make lint          Run ruff and mypy' \
		'  make lint-imports  Run the import smoke check' \
		'  make smoke-endpoint  Send a hello-world prompt to the live endpoint' \
		'  make test          Run pytest with 100%% coverage gating' \
		'  make test-<expr>   Run pytest -k <expr>' \
		'  make check         Run lint and test' \
		'  make validate      Run lint, test, and score checks' \
		'  make score-repo    Run the self-contained architecture scorecard' \
		'  make hello         Send a quick hello prompt to Claude'

hello:
	$(PYTHON) main.py "Say hello"

version:
	@$(PYTHON) -c 'import main; print(main.__version__)'

install:
	$(UV) sync --group dev

format:
	$(UV) run ruff format main.py tests scripts

lint:
	$(UV) run ruff check main.py tests scripts
	$(UV) run mypy main.py tests scripts

lint-imports:
	$(PYTHON) scripts/check_imports.py

smoke-endpoint:
	$(PYTHON) main.py "Say hello in five words"

test:
	$(UV) run pytest --cov=main --cov-report=term-missing --cov-fail-under=$(COV_FAIL_UNDER)

test-%:
	$(UV) run pytest -k "$*"

check: lint test

validate: check score-repo

score-repo:
	$(PYTHON) scripts/score_repo.py --min-score 8
