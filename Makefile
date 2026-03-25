.PHONY: dev down logs test health lint fmt build prod test-ci

dev:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend python -m pytest tests/ -x -q

health:
	@curl -s http://localhost:8000/api/health/ready | python3 -m json.tool

lint:
	cd backend && python -m ruff check src/ tests/

fmt:
	cd backend && python -m ruff format src/ tests/

build:
	docker compose build

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

test-ci:
	docker compose run --rm --no-deps backend python -m pytest tests/ -v -m "not benchmark"
