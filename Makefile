.PHONY: clean clean-test clean-pyc clean-build docs help

help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n\nTargets:\n"} /^[+a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
install: ## install
	poetry install 
test: install ## run test
	poetry run pytest --benchmark-skip
bench: install ## run benchmark
	poetry run pytest --benchmark-only
build: ## build
	rm -rf dist
	poetry build -f wheel
