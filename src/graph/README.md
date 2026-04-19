# Graph read API verification plan

first-stage graph visualization read surface on top of the
existing projector/read model.

## Endpoint contract to verify

- `GET /graph/meta` — aggregated node/edge counts, available node types,
  supported relationship types, checkpoint mirror
- `GET /graph/search?q=<term>&limit=<n>` — ranked node search results for graph
  visualization entrypoints
- `GET /graph/nodes/{node_type}/{node_id}/neighbors?limit=<n>` — one-hop
  neighborhood around a center node
- `GET /graph/subgraph?node_type=<type>&node_id=<id>&depth=<n>&limit=<n>` —
  bounded subgraph centered on a node
