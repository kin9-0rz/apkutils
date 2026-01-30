.PHONY: clean clean-test clean-pyc clean-build docs help

help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n\nTargets:\n"} /^[+a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
sync: ## sync
	uv sync
test: sync ## run test
	uv run pytest --benchmark-skip
bench: sync ## run benchmark
	uv run pytest --benchmark-only
build: ## build
	rm -rf dist
	uv build --wheel
