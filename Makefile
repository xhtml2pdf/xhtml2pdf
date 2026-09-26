.PHONY: help setup devsetup clean clean-pyc clean-build list test test-all test-ref test-render test-render-all test-browser test-browser-update perf perf-scaling perf-golden perf-golden-update docs release sdist

# Virtualenv used by setup/devsetup. Override with e.g. `make setup VENV=.venv312`.
VENV ?= .venv
PIP := $(VENV)/bin/pip

# The targets that run the code prepare that virtualenv before they run, and
# put it first on PATH, so the plain "python" of their recipes is its
# interpreter, after a cd too. Not in CI, which installs into the runner's
# Python with a pinned reportlab, nor inside a virtualenv already active: both
# run with the Python they have.
ifeq ($(CI)$(VIRTUAL_ENV),)
ENV := $(VENV)/.installed
BROWSER_ENV := $(VENV)/.installed-browser
export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)
endif

help:
	@echo "setup - create a venv and install xhtml2pdf in editable mode"
	@echo "devsetup - setup, plus test/docs/release extras (build, twine, ...) and pre-commit hooks"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"
	@echo "test-ref - create reference directory for testrender"
	@echo "test-render - compare testrender output against the reference (needs test-ref)"
	@echo "test-render-all - create the reference and compare in one go"
	@echo "test-browser - compare output against a browser rendering the same result"
	@echo "test-browser-update - re-record the browser comparison baseline"
	@echo "perf - time the render of the benchmark corpus, phase by phase"
	@echo "perf-scaling - time the synthetic ladder that shows how cost grows"
	@echo "perf-golden - check the corpus still renders byte for byte"
	@echo "perf-golden-update - record the current render as that reference"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "sdist - package"

$(VENV)/bin/python:
	python3 -m venv $(VENV)

# What the test and perf targets need, installed again when pyproject.toml
# changes.
$(VENV)/.installed: pyproject.toml | $(VENV)/bin/python
	$(PIP) install --upgrade pip
	$(PIP) install -e .[test]
	touch $@

$(VENV)/.installed-browser: $(VENV)/.installed
	$(PIP) install -e .[test,browsertest]
	touch $@

# Base install: just the package itself, editable, for running/using xhtml2pdf.
setup: $(VENV)/bin/python
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	@echo "Virtualenv ready. Activate it with: source $(VENV)/bin/activate"

# Full development environment: test/docs/release extras (release pulls in
# build + twine) plus the pre-commit hooks declared in .pre-commit-config.yaml.
devsetup: $(VENV)/bin/python
	$(PIP) install --upgrade pip
	$(PIP) install -e .[test,docs,release]
	$(PIP) install pre-commit
	$(VENV)/bin/pre-commit install
	@echo "Dev virtualenv ready. Activate it with: source $(VENV)/bin/activate"

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

test: $(ENV)
	coverage run -m unittest discover -t . -s tests

test-render: $(ENV)
	cd testrender && python testrender.py --only-errors

# Convenience for local use. Note this compares the output against a reference
# built from the same commit and the same reportlab, so it only catches
# non-determinism; the real cross-version gate lives in CI.
test-render-all: test-ref test-render

# Compares against an external reference: a browser rendering the equivalent
# markup from testrender/data/browser/. The browser runs headless, so no window
# appears; xvfb-run is used when available purely as a safety net, so that
# --headed debugging runs land on a virtual display instead of the desktop.
XVFB := $(shell command -v xvfb-run 2>/dev/null)

test-browser: $(BROWSER_ENV)
	$(if $(XVFB),$(XVFB) -a,) python testrender/browsercompare.py --report

test-browser-update: $(BROWSER_ENV)
	$(if $(XVFB),$(XVFB) -a,) python testrender/browsercompare.py --update-baseline


# Deliberately not wired into `test` or into CI: a timing on a shared runner
# says more about the runner than about the change, and perf-golden only means
# anything next to a reference recorded before the change.
perf: $(ENV)
	python tools/perf/bench.py

perf-scaling: $(ENV)
	python tools/perf/bench.py --scaling

perf-golden: $(ENV)
	python tools/perf/golden.py

perf-golden-update: $(ENV)
	python tools/perf/golden.py --update

test-all:
	tox

test-ref: $(ENV)
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
