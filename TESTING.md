# Testing Guide

> 100% test coverage is the key to great vibe coding. Tests let you move fast, trust your instincts, and ship with confidence — without them, vibe coding is just yolo coding. With tests, it's a superpower.

## Framework

- **pytest** 9.x
- **pytest-cov** (coverage reporting)

## How to run tests

```bash
# Make sure dependencies are installed
uv pip install -r requirements.txt pytest pytest-cov

# Run all tests with coverage
PYTHONPATH=. .venv/bin/pytest tests/ -v --cov=app --cov-report=term-missing
```

## Test layers

| Layer | What | Where |
|-------|------|-------|
| Unit tests | Service/util logic in isolation | `tests/test_utils.py` |
| Integration tests | API endpoints with in-memory SQLite | `tests/test_auth.py`, `tests/test_project.py` |
| E2E tests | Browser flow automation (not yet set up) | — |

## Conventions

- Test files are named `test_*.py` under `tests/`.
- Fixtures live in `tests/conftest.py`.
- Use Flask `test_client()` for HTTP-level assertions.
- Use `app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"` for isolated DB state.

## Expectations

- When writing new functions, write a corresponding test.
- When fixing a bug, write a regression test.
- When adding error handling, write a test that triggers the error.
- When adding a conditional (if/else), write tests for BOTH paths.
- Never commit code that makes existing tests fail.
