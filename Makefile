.PHONY: dev down logs test health lint fmt build prod test-ci \
        neo4j neo4j-status neo4j-stop neo4j-wipe-nexis

# ─── Shared Neo4j (lives outside docker-compose) ────────────────────────────
# This project shares one host-level Neo4j container across sibling local
# projects to save RAM (~1.5GB per instance). Isolation is via Graphiti's
# group_id="nexis" namespacing. See docs/shared-neo4j.md.
NEO4J_CONTAINER := neo4j-shared
NEO4J_VOLUME    := neo4j-shared-data
NEO4J_PASSWORD  := shared-dev-password

dev: neo4j
	docker compose up -d

# Ensure the shared Neo4j container is running and ready.
# - creates the data volume if missing
# - creates the container if missing (with APOC + memory settings)
# - starts it if stopped
# - waits until cypher-shell answers before returning
neo4j:
	@if ! docker volume inspect $(NEO4J_VOLUME) >/dev/null 2>&1; then \
		echo "→ creating volume $(NEO4J_VOLUME)"; \
		docker volume create $(NEO4J_VOLUME) >/dev/null; \
	fi
	@if ! docker ps -a --format '{{.Names}}' | grep -qx "$(NEO4J_CONTAINER)"; then \
		echo "→ creating $(NEO4J_CONTAINER) on :7690 (host) → :7687 (container)"; \
		docker run -d --name $(NEO4J_CONTAINER) --restart unless-stopped \
			-p 7690:7687 -p 7475:7474 \
			-v $(NEO4J_VOLUME):/data \
			-e NEO4J_AUTH=neo4j/$(NEO4J_PASSWORD) \
			-e NEO4J_PLUGINS='["apoc"]' \
			-e NEO4J_server_memory_heap_initial__size=512m \
			-e NEO4J_server_memory_heap_max__size=1G \
			-e NEO4J_server_memory_pagecache_size=512m \
			neo4j:5 >/dev/null; \
	elif ! docker ps --format '{{.Names}}' | grep -qx "$(NEO4J_CONTAINER)"; then \
		echo "→ starting existing $(NEO4J_CONTAINER)"; \
		docker start $(NEO4J_CONTAINER) >/dev/null; \
	else \
		echo "→ $(NEO4J_CONTAINER) already running"; \
	fi
	@echo "→ waiting for Neo4j to accept queries..."
	@for i in $$(seq 1 60); do \
		if docker exec $(NEO4J_CONTAINER) cypher-shell -u neo4j -p $(NEO4J_PASSWORD) "RETURN 1" >/dev/null 2>&1; then \
			echo "✓ Neo4j ready at bolt://localhost:7690 (browser: http://localhost:7475)"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "✗ Neo4j did not become ready in 60s"; exit 1

neo4j-status:
	@docker ps -a --filter "name=$(NEO4J_CONTAINER)" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Does NOT stop the shared container by default — other projects may depend on it.
neo4j-stop:
	@echo "⚠  $(NEO4J_CONTAINER) is shared with other projects."
	@echo "   This will stop it for everyone. Continue? (ctrl-C to abort)"
	@read _
	docker stop $(NEO4J_CONTAINER)

# Wipe ONLY this project's data (group_id='nexis'), preserves sibling projects.
neo4j-wipe-nexis:
	docker exec $(NEO4J_CONTAINER) cypher-shell -u neo4j -p $(NEO4J_PASSWORD) \
		"MATCH (n) WHERE n.group_id = 'nexis' DETACH DELETE n;"

# `down` only stops the app stack; shared Neo4j is left running on purpose.
down:
	docker compose down
	@echo "ℹ  $(NEO4J_CONTAINER) left running (shared resource). Use 'make neo4j-stop' to stop."

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest tests/ -x -q

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
	cd backend && python -m pytest tests/ -v -m "not benchmark"
