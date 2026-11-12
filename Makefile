.DEFAULT_GOAL := setup

UV ?= uv
PYTHON_VERSION ?= 3.12

.PHONY: help setup check-uv

help:
	@printf '%s\n' \
	  'make setup   Create .venv and install all locked dependencies (default).' \
	  '             Includes development dependencies; downloads Python if needed.' \
	  '             Override Python with: make setup PYTHON_VERSION=3.13' \
	  'Activate with: source .venv/bin/activate'

check-uv:
	@command -v "$(UV)" >/dev/null 2>&1 || { \
	  printf '%s\n' 'uv is required. Install it with: brew install uv' \
	    'Other platforms: https://docs.astral.sh/uv/getting-started/installation/'; \
	  exit 1; \
	}

setup: check-uv
	$(UV) sync --locked --all-groups --python "$(PYTHON_VERSION)"
	@printf '\n%s\n' 'Setup complete. Activate with: source .venv/bin/activate'
