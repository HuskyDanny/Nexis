.PHONY: dev down logs test health lint fmt

dev:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose exec backend python -m pytest tests/ -x -q

health:
	@curl -s http://localhost:8000/api/health | python3 -m json.tool

lint:
	cd backend && python -m ruff check src/ tests/

fmt:
	cd backend && python -m ruff format src/ tests/
