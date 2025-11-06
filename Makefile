.PHONY: all help lint format test test-unit test-functional clean

# Default target: run linting and all tests
all: lint test
	@echo "✓ All checks passed!"

help:
	@echo "Available targets:"
	@echo "  make (or all)  - Run lint and all tests (default)"
	@echo "  lint           - Check code formatting with black"
	@echo "  format         - Auto-format code with black"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-functional - Run functional tests only"
	@echo "  test           - Run all tests (unit + functional)"
	@echo "  clean          - Remove test artifacts and cache"

lint:
	@echo "Checking code formatting with black..."
	black --check --line-length 100 .

format:
	@echo "Formatting code with black..."
	black --line-length 100 .

test-unit:
	@echo "Running unit tests..."
	pytest tests/test_unit.py -v

test-functional:
	@echo "Running functional tests..."
	pytest tests/test_functional.py -v

test: test-unit test-functional
	@echo "All tests completed!"

clean:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf test-output
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
