#################################################################################
# GLOBALS                                                                       #
#################################################################################
include Makefile.include
#################################################################################
# Environment                                                                   #
#################################################################################
include Makefile.envs


#################################################################################
# Text Helpers                                                               	#
#################################################################################
TERMINATOR := \033[0m
WARNING := \033[1;33m [WARNING]:
INFO := \033[1;33m [INFO]:
HINT := \033[3;33m
SUCCESS := \033[1;32m [SUCCESS]:

#################################################################################
# Conda                                                                   		#
#################################################################################
ifeq (,$(CONDA_EXE))
HAS_CONDA=False
else
HAS_CONDA=True
endif

#################################################################################
# Virtual Environments															#
#################################################################################
.PHONY: build-env build-env-dev build-env-docs build-env-prod setup setup-dev setup-docs setup-prod

## Build main virtual environment and install dependencies
build-env:
	@echo -e "$(INFO) Creating virtual environment...$(TERMINATOR)" && \
	python3 -m venv .venv && \
	source .venv/bin/activate && \
	pip install --upgrade pip setuptools && \
	poetry install && \
	echo -e "$(SUCCESS) Virtual environment created successfully!$(TERMINATOR)" && \
	echo -e "$(HINT) Activate the virtual environment with: source .venv/bin/activate$(TERMINATOR)"

## Build development virtual environment and install dependencies
build-env-dev:
	@echo -e "$(INFO) Creating development virtual environment...$(TERMINATOR)" && \
	python3 -m venv .venv && \
	source .venv/bin/activate && \
	pip install --upgrade pip setuptools && \
	poetry install --with dev,notebook && \
	echo -e "$(SUCCESS) Virtual environment created successfully!$(TERMINATOR)" && \
	echo -e "$(HINT) Activate the virtual environment with: source .venv/bin/activate$(TERMINATOR)"

## Build documentation virtual environment and install dependencies
build-env-docs:
	@echo -e "$(INFO) Creating documentation virtual environment...$(TERMINATOR)" && \
	python3 -m venv .venv-docs && \
	source .venv-docs/bin/activate && \
	pip install --upgrade pip setuptools && \
	poetry install --with dev,docs && \
	echo -e "$(SUCCESS) Virtual environment created successfully!$(TERMINATOR)" && \
	echo -e "$(HINT) Activate the virtual environment with: source .venv-docs/bin/activate$(TERMINATOR)"

# Build production virtual environment and install dependencies
build-env-prod:
	@echo -e "$(INFO) Creating production virtual environment...$(TERMINATOR)" && \
	python3 -m venv .venv-prod && \
	source .venv-prod/bin/activate && \
	pip install --upgrade pip setuptools && \
	poetry install --with prod --no-cache && \
	echo -e "$(SUCCESS) Virtual environment created successfully!$(TERMINATOR)" && \
	echo -e "$(HINT) Activate the virtual environment with: source .venv-prod/bin/activate$(TERMINATOR)"


## Prepare development environment
setup: build-env
setup-dev: build-env-dev
setup-docs: build-env-docs
setup-prod: build-env-prod

#################################################################################
# Update Dependencies															#
#################################################################################
.PHONY: update-requirements update-requirements-dev update-requirements-docs update-requirements-prod update-requirements-all

install-export-plugin:
	@echo -e "$(INFO) Installing export plugin...$(TERMINATOR)" && \
	poetry self add poetry-plugin-export && \
	echo -e "$(SUCCESS) Export plugin installed successfully!$(TERMINATOR)"

## Update project main requirements
update-requirements: install-export-plugin
	@echo -e "$(INFO) Updating requirements file...$(TERMINATOR)" && \
	poetry export --only main --without-hashes -f requirements.txt -o requirements/requirements.txt && \
	poetry export --only prod --without-hashes -f requirements.txt -o requirements/requirements-prod.txt && \
	echo -e "$(SUCCESS) Requirements updated successfully!$(TERMINATOR)"

## Update project development requirements
update-requirements-dev: install-export-plugin
	@echo -e "$(INFO) Updating development requirements file...$(TERMINATOR)" && \
	poetry export --only dev --without-hashes -f requirements.txt -o requirements/requirements-dev.txt && \
	echo -e "$(SUCCESS) Requirements updated successfully!$(TERMINATOR)"

## Update project documentation requirements
update-requirements-docs: install-export-plugin
	@echo -e "$(INFO) Updating documentation requirements file...$(TERMINATOR)" && \
	poetry export --only docs --without-hashes -f requirements.txt -o requirements/requirements-docs.txt && \
	echo -e "$(SUCCESS) Requirements updated successfully!$(TERMINATOR)"

update-requirements-prod: install-export-plugin
	@echo -e "$(INFO) Updating production requirements file...$(TERMINATOR)" && \
	poetry export --only prod --without-hashes -f requirements.txt -o requirements/requirements-prod.txt && \
	echo -e "$(SUCCESS) Requirements updated successfully!$(TERMINATOR)"


## Update all project requirements
update-requirements-all: update-requirements update-requirements-dev update-requirements-docs update-requirements-prod

#################################################################################
# Pre-commit																	#
#################################################################################
.PHONY: install-pre-commit uninstall-pre-commit

## Install pre-commit hooks
install-pre-commit: build-env-dev
	@echo -e "$(INFO) Setting up pre-commit hooks...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run pre-commit install --install-hooks -t pre-commit -t commit-msg && \
	poetry run pre-commit autoupdate && \
	echo -e "$(SUCCESS) Setup complete!$(TERMINATOR)"

## Remove pre-commit hooks
uninstall-pre-commit:
	@echo -e "$(INFO) Removing pre-commit hooks...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run pre-commit uninstall && \
	poetry run pre-commit uninstall --hook-type pre-push && \
	rm -rf .git/hooks/pre-commit && \
	echo -e "$(SUCCESS) Pre-commit hooks removed!$(TERMINATOR)"

#################################################################################
# Cleanup																		#
#################################################################################
.PHONY: clean clean-test clean-hydra clean-all

## Remove build and Python artifacts
clean:
	rm -rf .venv*
	find . -type f -name '*.pyc' -delete
	find . -type f -name "*.DS_Store" -ls -delete
	find . -type f -name '*~' -exec rm -f {} +
	find . | grep -E "(__pycache__|\.pyc|\.pyo)" | xargs rm -rf
	find . | grep -E ".pytest_cache" | xargs rm -rf
	find . | grep -E ".ipynb_checkpoints" | xargs rm -rf

## Remove test, coverage artifacts
clean-test:
	rm -fr .tox/
	rm -fr .nox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache

## Remove hydra outputs
clean-hydra:
	rm -rf outputs
	rm -rf runs
	rm -rf multirun
	rm -rf mlruns

## Remove all artifacts
clean-all: clean clean-test clean-hydra

#################################################################################
# Testing																		#
#################################################################################
.PHONY: test format-check format-fix coverage coverage-html lint check-safety

## Run Pytest tests
test: build-env-dev
	@echo -e "$(INFO) Running tests...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run pytest -vvv tests/

## Verify formatting style
format-check: build-env-dev
	@echo -e "$(INFO) Checking code formatting...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run isort --check-only src/ && \
	poetry run black --check src/ && \

## Fix formatting style. This updates files
format-fix: build-env-dev
	@echo -e "$(INFO) Fixing code formatting...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run isort src/ && \
	poetry run black src/ && \

## Generate test coverage reports
coverage: build-env-dev
	@echo -e "$(INFO) Running coverage...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run pytest --cov=src/ test/ && \
	poetry run coverage report

## Generate HTML coverage report
coverage-html: coverage
	@echo -e "$(INFO) Generating HTML coverage report...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run coverage html

## Check code for lint errors
lint: build-env-dev
	@echo -e "$(INFO) Running linters...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run flake8 src/ && \
	poetry run mypy src/

## Check for package vulnerabilities
check-safety: build-env-dev
	@echo -e "$(INFO) Checking dependencies for security vulnerabilities...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run safety check -r requirements/requirements.txt && \
	poetry run safety check -r requirements/requirements-prod.txt && \
	poetry run bandit -ll --recursive hooks

#################################################################################
# Version Control																#
#################################################################################
.PHONY: commit push bump bump_major bump_minor bump_micro jenkins_bump changelog change-version release dvc-download dvc-upload push-all

## Commit using Conventional Commit with Commitizen
commit:
	@echo -e "$(INFO) Committing changes with Commitizen...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run cz commit

## Git push code and tags
push:
	@echo -e "$(INFO) Pushing changes to remote...$(TERMINATOR)" && \
	git push && \
	git push --tags

## Bump semantic version based on the git log
bump:
	@echo -e "$(INFO) Bumping version...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run cz bump

## Bump to next major version (e.g. X.Y.Z -> X+1.Y.Z)
bump_major:
	echo "$(CURRENT_VERSION_MAJOR)" > VERSION

## Bump to next minor version (e.g. Y.X.Y -> Y.X+1.Y)
bump_minor:
	echo "$(CURRENT_VERSION_MINOR)" > VERSION

## Bump to next micro version (e.g. Y.Y.X -> Y.Y.X+1)
bump_micro:
	echo "$(CURRENT_VERSION_MICRO)" > VERSION

## Jenkins version bump
jenkins_bump:
	@git config --global user.email "-"
	@git config --global user.name "Jenkins"
	@(git tag --sort=-creatordate | grep -E '^\d+\.\d+\.\d+$$' || echo '0.0.0') | head -n 1 > VERSION
	@/scripts/bump $$(git log -1 --pretty=%B)
	@git tag $$(cat VERSION)
	@git push origin $$(cat VERSION)

## Generate changelog
changelog:
	@echo -e "$(INFO) Generating changelog...$(TERMINATOR)" && \
	source .venv/bin/activate && \
	poetry run cz changelog

## Release new version.
release:
	git commit -am "bump: Release code version $(VERSIONFILE)"
	git tag -a v$(VERSIONFILE) -m "bump: Release tag for version $(VERSIONFILE)"
	git push
	git push --tags

## Change to previous model and data version (e.g. make change-version v="0.1.0")
change-version:
	git checkout v$v && \
	dvc checkout

## Get data from DVC remote
dvc-download:
	dvc pull

## Push data to DVC remote
dvc-upload:
	dvc push

## Push code and data
dvc-push-all: push dvc-upload

#################################################################################
# Documentation																	#
#################################################################################
.PHONY: mkdocs-build mkdocs-serve mkdocs-clean

## Generate MKDocs documentation
mkdocs-build: mkdocs-build
	@echo -e "$(INFO) Building documentation...$(TERMINATOR)" && \
	source .venv-docs/bin/activate && \
	cp README.md docs/index.md && \
	poetry run mkdocs build

## Serve MKDocs documentation on localhost:8000
mkdocs-serve:
	@echo -e "$(INFO) Serving documentation...$(TERMINATOR)" && \
	source .venv-docs/bin/activate && \
	poetry run mkdocs serve

## Clean MKDocs documentation
mkdocs-clean:
	rm -rf site/

#################################################################################
# Help																			#
#################################################################################
.DEFAULT_GOAL := help

.PHONY: help

## Show this help message
help:
	@echo "$$(tput bold)              ** Available rules: ** $$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=25 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf " - %s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
