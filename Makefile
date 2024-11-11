
.DEFAULT_GOAL := help

.PHONY : help
help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)


install: ## Install dependencies
	pip install --require-virtualenv .
	pip install --require-virtualenv flake8 pytest pytest-cov pytest-html
	pip install --require-virtualenv sphinx sphinxcontrib-images sphinx-rtd-theme==1.2.0
	pip install --require-virtualenv nbsphinx
	pip install --require-virtualenv nbsphinx_link ipython
	pip install --require-virtualenv wheel twine build
# pip install --require-virtualenv mypy pandas-stubs types-Pygments types-colorama types-decorator types-jsonschema types-six

lint: ## Linting with flake8
	flake8 scanpro setup.py tests --ignore=E501,W503 --extend-exclude=scanpro/__init__.py

test: ## Unittesting
	pytest -v --color=yes --import-mode=importlib --cov-report=term --cov --cov-report html:htmlcov

.PHONY : build
build: ## Build package and check with twine
# Uninstall package
	pip uninstall scanpro -y --quiet

# Install and update build dependencies
	pip install --upgrade pip wheel twine build

# Build package
	python setup.py build_ext --inplace
	python setup.py sdist

# Check package build
	twine check dist/*

# reinstall package
	pip install --require-virtualenv .

check: install lint typing build test ## Run all checks

typing: ## Check typing with mypy
	mypy scanpro
