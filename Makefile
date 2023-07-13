coverage:
	pytest --cov=payfast --cov-report html

build:
	python3 -m build && \
	pip install twine --upgrade && \
	twine upload dist/*
