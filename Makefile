.PHONY: help clean clean-pyc clean-build list test test-all docs release sdist

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "testall - run tests on every Python version with tox"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "sdist - package"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

lint:
	pep8 xhtml2pdf

test:
	python setup.py nosetests

test-all:
	tox

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	sphinx-build -b linkcheck ./docs _build/
	sphinx-build -b html ./docs _build/

release: clean
	python setup.py sdist bdist_wheel
	twine upload -s dist/*

sdist: clean
	python setup.py sdist
	ls -l dist
