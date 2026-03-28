# Backend

FastAPI backend with [Restate](https://restate.dev/) for durable orchestration.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Restate server: `brew install restatedev/tap/restate-server`

## Setup

Install dependencies:

```bash
uv sync
```

Recommended environment variables:

```bash
export OPENAI_API_KEY=...
export TINYFISH_API_KEY=...
export RESTATE_INGRESS_URL=http://localhost:8080
export RESTATE_ADMIN_URL=http://localhost:9070
export SELF_URL=http://localhost:8000
```

Optional:

```bash
export RESTATE_AUTO_REGISTER=true
export OPENAI_EXPLORER_MODEL=gpt-5
export EXPLORER_MAX_DEPTH=1
export EXPLORER_MAX_SUB_EXPLORERS=2
export EXPLORER_MAX_RESULTS=10
export EXPLORER_SEED_LIMIT=8
export EXPLORER_DOMAIN_LIMIT=24
export EXPLORER_ENUM_TLDS=com,org,net,co
```

## Running

1. Start Restate:

```bash
restate-server
```

Or with Docker:

```bash
docker run --name restate_dev --rm -p 8080:8080 -p 9070:9070 -p 9071:9071 docker.io/restatedev/restate:latest
```

2. Start the backend:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

The app auto-registers its `/restate` deployment on startup. Set `RESTATE_AUTO_REGISTER=false` if you want to disable that behavior.

## API

- `POST /api/search`
- `GET /api/search/{job_id}`
- `GET /api/search/{job_id}/events`
- `GET /openapi.json`

Example kickoff request:

```bash
curl -X POST http://localhost:8000/api/search \
  -H 'content-type: application/json' \
  -d '{
    "query": {
      "text": "embroidered denim underground brands",
      "profile": {
        "style": ["avant-garde", "DIY"],
        "avoid": ["mass market"]
      }
    }
  }'
```

## OpenAPI

Export the committed spec artifacts:

```bash
uv run python -m backend.export_openapi
```

This writes:

- `openapi/openapi.json`
- `openapi/openapi.yaml`

## Tests

Run the backend test suite:

```bash
RESTATE_AUTO_REGISTER=false uv run python -m unittest discover -s tests -v
```
