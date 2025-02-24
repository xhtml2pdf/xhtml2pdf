.PHONY: help clean clean-pyc clean-build list test test-all docs release sdist

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"
	@echo "test-ref - create reference directory for testrender"
	@echo "test-render - run testrender tests"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "sdist - package"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr test/test_working
	rm -fr testrender/data/test_working

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

lint:
	pep8 xhtml2pdf

test:
	coverage run -m unittest discover tests

test-render:
	cd testrender && python testrender.py --only-errors


test-all:
	tox

test-ref:
	cd testrender && python testrender.py --create-reference data/reference

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	sphinx-build -b linkcheck ./docs/source _build/
	sphinx-build -b html ./docs/source _build/

release: clean
	git tag -a "v`xhtml2pdf --version`" -m "Bump version `xhtml2pdf --version`"
	git push origin "v`xhtml2pdf --version`"
	python -m build
	twine upload -s dist/*

sdist: clean
	python -m build --sdist
	ls -l dist
