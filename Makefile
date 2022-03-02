.PHONY: clean clean-test clean-pyc clean-build docs help

help: ## 帮助
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n\nTargets:\n"} /^[+a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: clean ## 安装包
	@poetry install
	@poetry run apkutils --version
	@poetry run apkutils --help

test: install ## 跑测试
	poetry run pytest --benchmark-skip --ignore=setup.py
benchmark: ## 基准测试
	poetry run pytest tests/test_benchmark.py
tox: ## tox
	poetry run tox
build: ## build
	rm -rf dist
	poetry build -f wheel
