# Shared Neo4j Dev Instance

This project does **not** run its own Neo4j inside `docker-compose`. It connects to
a single `neo4j-shared` container running on the host, which is also used by
sibling local projects (e.g., `experiemnt_zep_rag`). Isolation between projects is
enforced via Graphiti's `group_id` namespacing — this project uses `group_id="nexis"`.

## Connection

| Context | URI |
|---|---|
| Host-run backend (`.env.base`) | `bolt://localhost:7690` |
| `docker-compose` backend | `bolt://host.docker.internal:7690` |
| User | `neo4j` |
| Password | `shared-dev-password` |
| Browser UI | `http://localhost:7475` |

`docker-compose.yml` injects `extra_hosts: host.docker.internal:host-gateway` so
the backend container can reach the host's 7690 port on Linux as well as macOS.

## Starting / Managing the Shared Instance

One-time setup:

```bash
docker volume create neo4j-shared-data
docker run -d --name neo4j-shared --restart unless-stopped \
  -p 7690:7687 -p 7475:7474 \
  -v neo4j-shared-data:/data \
  -e NEO4J_AUTH=neo4j/shared-dev-password \
  -e NEO4J_PLUGINS='["apoc"]' \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=1G \
  -e NEO4J_server_memory_pagecache_size=512m \
  neo4j:5
```

Ready check:

```bash
docker exec neo4j-shared cypher-shell -u neo4j -p shared-dev-password "RETURN 1"
```

## Inspect / Wipe Only This Project's Data

Namespace is `group_id="nexis"`. To wipe just this project's data without affecting
siblings:

```cypher
MATCH (n) WHERE n.group_id = 'nexis' DETACH DELETE n;
```

To count nodes per group (sanity check when multiple projects share the DB):

```cypher
MATCH (n) WITH n.group_id AS gid, count(*) AS c RETURN gid, c ORDER BY c DESC;
```

## Migration History

- **Before:** this stack ran its own `neo4j:5.26-community` service inside
  `docker-compose.yml` with volume `neo4j_data`, exposed on host port 7687,
  password `nexis-dev-password`.
- **Migration (2026-04-17):** data copied volume-to-volume
  (`cron-prepopulate_neo4j_data` → `neo4j-shared-data`), container recreated on
  port 7690 with APOC and matching memory settings, password rotated to
  `shared-dev-password`. 265 Episodic + 228 Entity nodes preserved, all with
  `group_id="nexis"`.
- The old `cron-prepopulate_neo4j_data` volume is retained for now as a backup.

## Rollback

If the shared instance becomes problematic, revert by restoring the `neo4j`
service block in `docker-compose.yml` (see git history) and pointing
`NEO4J_URI` back to `bolt://neo4j:7687`. Data in the shared instance for
`group_id="nexis"` can be copied back via the same volume-copy technique.
