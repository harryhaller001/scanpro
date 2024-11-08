.DEFAULT_GOAL := test

install: ## Install dependencies
	pip install --require-virtualenv .
	pip install --require-virtualenv flake8 pytest pytest-cov pytest-html
	pip install --require-virtualenv sphinx sphinxcontrib-images sphinx-rtd-theme==1.2.0
	pip install --require-virtualenv nbsphinx
	pip install --require-virtualenv nbsphinx_link ipython
	pip install --require-virtualenv wheel twine build

lint: ## Linting with flake8
	flake8 scanpro setup.py tests --ignore=E501,W503 --extend-exclude=scanpro/__init__.py

test: ## Unittesting
	pytest -v --color=yes --import-mode=importlib --cov-report=term --cov --cov-report html:htmlcov

.PHONY : build
build: ## Build package and check with twine
	pip install --upgrade pip wheel twine build
	python setup.py build_ext --inplace
	python setup.py sdist
	twine check dist/*

check: install lint test build ## Run all checks
