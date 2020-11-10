.PHONY: lint types black clean

lint:
	@python -m flake8 --exclude=.git,venv* scrapy_playwright/*.py tests/*.py

types:
	@mypy --ignore-missing-imports --follow-imports=skip scrapy_playwright/*.py tests/*.py

black:
	@black --check scrapy_playwright tests

clean:
	@find . -name "*.pyc" -delete
	@rm -rf .mypy_cache/ .tox/ build/ dist/ htmlcov/ .coverage coverage.xml
