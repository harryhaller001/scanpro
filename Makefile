.DEFAULT_GOAL := test

install:
	pip install --require-virtualenv .
	pip install --require-virtualenv flake8 pytest pytest-cov pytest-html

lint:
	flake8 scanpro setup.py tests --ignore=E501,W503 --extend-exclude=scanpro/__init__.py

test:
	pytest -v --color=yes --import-mode=importlib --cov-report=term --cov --cov-report html:htmlcov
