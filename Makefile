.PHONY: install test lint clean

install:
	uv pip install -e ".[dev]"

test:
	python -m pytest tests/ -v --tb=short

lint:
	python -m compileall src/dockerbrain/
	@echo "All files compile OK"

clean:
	rm -rf build/ dist/ *.egg-info *.whl __pycache__ src/dockerbrain/__pycache__ tests/__pycache__
	rm -rf .pytest_cache htmlcov/ .coverage
