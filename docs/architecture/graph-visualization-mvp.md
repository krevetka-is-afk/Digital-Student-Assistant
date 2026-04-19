# Graph visualization MVP contract

Updated: 2026-04-19

## Scope

This document captures the **first-stage** backend contract for graph visualization,
grounded in the current `src/graph` projector/read model. It is intentionally
minimal: seed search, shallow subgraph fetch, node-neighbor expansion, and graph
metadata/freshness.

The contract assumes the current Neo4j projection owned by `src/graph/app/graph_store.py`.
It does **not** introduce pathfinding, analytics, or write-through graph mutation.

## Concise implementation plan

1. **Add read DTOs and serializers**
   - Extend `src/graph/app/models.py` with response models for nodes, edges, search hits,
     subgraph payloads, and graph meta.
2. **Extend the read-model boundary**
   - Add `search`, `subgraph`, `neighbors`, and `meta` methods to the `GraphStore`
     protocol and `Neo4jGraphStore`.
   - Keep query logic inside the store so FastAPI handlers remain thin.
3. **Expose FastAPI read endpoints**
   - Add `GET /search`, `GET /subgraph`, `GET /neighbors`, and `GET /meta` in
     `src/graph/app/main.py`.
   - Reuse the existing app-state graph store/projector wiring.
4. **Verify with service-level tests**
   - Extend `src/graph/tests/integration/test_projector.py` with a fake read store
     and endpoint-level tests for the new response shapes.

## Read-model assumptions

### Node types

The visualization layer should only expose node kinds already present in the read model:

- `student`
- `project`
- `application`
- `supervisor`
- `tag`

### Stable client-facing IDs

Frontend-facing IDs should be serialized as composite strings to avoid collisions:

- `student:<student_id>`
- `project:<project_id>`
- `application:<application_id>`
- `supervisor:<supervisor_key>`
- `tag:<tag_name_normalized>`

The original domain key should also be returned separately as `entity_id`.

### Supported edge types

- `SUPERVISED_BY`
- `TAGGED_WITH`
- `INTERESTED_IN`
- `SUBMITTED`
- `TARGETS`

## Endpoint contract

### 1. `GET /search`

Purpose: resolve an initial node set from a free-text query before loading a graph.

#### Query params

- `q` — required search string
- `limit` — optional, default `10`, max `50`
- `types` — optional repeated filter (`student`, `project`, `application`, `supervisor`, `tag`)

#### MVP behavior

- Case-insensitive substring match over currently projected properties only.
- No full-text index requirement for the first slice.
- Ranking can stay heuristic and deterministic:
  1. exact identifier match
  2. prefix match
  3. substring match
  4. type/name tie-break

#### Response shape

```json
{
  "query": "graph",
  "items": [
    {
      "id": "project:11",
      "entity_id": "11",
      "kind": "project",
      "label": "Graph analytics for student teams",
      "match_reason": "title",
      "score": 1.0,
      "meta": {
        "status": "published",
        "tags": ["neo4j", "graph"]
      }
    }
  ]
}
```

### 2. `GET /subgraph`

Purpose: return a bounded graph around one or more seed nodes.

#### Query params

- `seed` — required repeated node IDs in composite form (`project:11`)
- `depth` — optional, default `1`, max `2`
- `limit` — optional hard cap for total returned nodes, default `100`, max `300`
- `edge_types` — optional repeated relationship filter

#### MVP behavior

- Shallow traversal only (`depth <= 2`)
- Deduplicate nodes/edges server-side
- Return a single canonical graph payload that the frontend can render directly

#### Response shape

```json
{
  "seeds": ["project:11"],
  "depth": 1,
  "nodes": [
    {
      "id": "project:11",
      "entity_id": "11",
      "kind": "project",
      "label": "Graph analytics for student teams",
      "meta": {
        "status": "published"
      }
    },
    {
      "id": "tag:graph",
      "entity_id": "graph",
      "kind": "tag",
      "label": "graph",
      "meta": {}
    }
  ],
  "edges": [
    {
      "id": "project:11|TAGGED_WITH|tag:graph",
      "source": "project:11",
      "target": "tag:graph",
      "kind": "TAGGED_WITH"
    }
  ]
}
```

### 3. `GET /neighbors`

Purpose: expand one already-rendered node without refetching the whole graph.

#### Query params

- `node_id` — required composite node ID
- `limit` — optional, default `50`, max `100`
- `edge_types` — optional repeated relationship filter

#### Response shape

Same node/edge contract as `/subgraph`, but limited to one-hop results:

```json
{
  "node_id": "project:11",
  "nodes": [],
  "edges": []
}
```

### 4. `GET /meta`

Purpose: expose graph freshness and lightweight topology metadata for the UI.

#### Response shape

```json
{
  "status": "ok",
  "consumer": "graph",
  "checkpoint": {
    "last_acked_event_id": 12,
    "updated_at": "2026-04-19T14:00:00Z"
  },
  "counts": {
    "student": 15,
    "project": 42,
    "application": 9,
    "supervisor": 8,
    "tag": 27,
    "edges": 103
  },
  "capabilities": {
    "search": true,
    "subgraph": true,
    "neighbors": true,
    "depth_max": 2
  }
}
```

## Frontend usage assumptions

The MVP frontend should assume:

1. **Search is the entrypoint**
   - call `/search` first to resolve the initial seed node(s)
2. **`/meta` drives freshness UI**
   - use checkpoint/counts for badges, empty states, and stale-data hints
3. **Client graph state is append/merge based**
   - `/subgraph` returns the initial canvas payload
   - `/neighbors` appends one-hop expansions
4. **Client dedup is by `id`**
   - node and edge IDs are stable and globally unique within the rendered graph
5. **Labels are display-safe**
   - use `label` for immediate rendering; deeper properties live under `meta`
6. **No analytics promises in phase 1**
   - no shortest-path, centrality, clustering, or force-layout instructions from the backend

## Known MVP gaps / non-goals

- No full-text index requirement yet
- No pagination cursor contract for graph traversal
- No cross-service authorization rules beyond the existing service boundary
- No graph mutation API
- No guarantee that every Django-side field is mirrored into Neo4j; only projected properties are searchable/renderable

## Recommendation for review

Before implementation, keep reviewers aligned on:

- exact query-param names (`seed` vs `seed_ids`, `types` vs `kinds`)
- whether `/search` should remain `GET` or switch to `POST` once filters become nested
- maximum payload limits for `subgraph` and `neighbors`
- whether `meta.checkpoint` should mirror `/state` directly or use a dedicated read model
