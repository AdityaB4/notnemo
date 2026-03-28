# Backend

FastAPI backend with [Restate](https://restate.dev/) for durable orchestration.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)

## Setup

Install dependencies:

```bash
uv sync
```

Create a `.env.local` file in the backend directory with your secrets:

```bash
OPENAI_API_KEY=...
TINYFISH_API_KEY=...
```

Optional environment variables (with defaults):

```bash
export RESTATE_INGRESS_URL=http://localhost:8080
export RESTATE_ADMIN_URL=http://localhost:9070
export SELF_URL=http://localhost:8000
export RESTATE_AUTO_REGISTER=true
export DATABASE_URL=
export OPENAI_EXPLORER_MODEL=gpt-5
export EXPLORER_MAX_DEPTH=1
export EXPLORER_MAX_SUB_EXPLORERS=2
export EXPLORER_MAX_RESULTS=10
export EXPLORER_SEED_LIMIT=8
export EXPLORER_DOMAIN_LIMIT=24
export EXPLORER_SSE_POLL_MS=250
export EXPLORER_ENUM_TLDS=com,org,net,co
export BRAINTRUST_API_KEY=
export BRAINTRUST_PROJECT=notnemo
```

## Running

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

The app auto-registers its `/restate` deployment with the Restate server on startup. Set `RESTATE_AUTO_REGISTER=false` to disable this.

## API

- `POST /api/search` — kick off a search job
- `GET /api/search/{job_id}` — get a snapshot of a search job
- `GET /api/search/{job_id}/events` — SSE stream of search progress
- `GET /health` — health check
- `GET /db` — database/pgvector status
- `GET /openapi.json`

Example:

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

Export the OpenAPI spec:

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

## Manual CLI

The manual CLI lives at `scripts/search_cli.py`. Run it from the `backend/`
directory after the API is up on `http://localhost:8000` unless you pass a
different `--base-url`.

It does three things in sequence:

1. `POST /api/search` with your request payload
2. Optionally stream `GET /api/search/{job_id}/events`
3. Fetch and print the final `GET /api/search/{job_id}` snapshot

### How To Use It

Use plain-text mode when you only need a query string plus an optional profile:

```bash
uv run python scripts/search_cli.py "embroidered denim underground brands" \
  --base-url http://localhost:8000 \
  --profile-json '{"style":["avant-garde","DIY"],"avoid":["mass market"]}'
```

Use full-payload mode when you want to control the request body directly. This
is the most useful mode for testing limits and reproducing API behavior:

```bash
uv run python scripts/search_cli.py \
  --base-url http://localhost:8000 \
  --payload-json '{
    "query": {
      "text": "embroidered denim underground brands",
      "profile": {
        "style": ["avant-garde", "DIY"],
        "avoid": ["mass market"]
      }
    },
    "limits": {
      "max_results": 5

    }
  }'
```

If the payload is large, put it in a file and pass `--payload-file` instead of
embedding JSON in the shell command:

```bash
uv run python scripts/search_cli.py \
  --base-url http://localhost:8000 \
  --payload-file ./fixtures/search-request.json
```

To force a TinyFish tool call during manual testing, add the debug hint below.
The explorer will still do a web search first, then it must call
`tinyfish_scrape` before it finalizes results:

```bash
uv run python scripts/search_cli.py \
  --base-url http://localhost:8000 \
  --payload-json '{
    "query": {
      "text": "embroidered denim underground brands from community and editorial sources",
      "profile": {
        "style": ["avant-garde", "DIY"],
        "avoid": ["mass market"],
        "debug_force_tinyfish": true
      }
    },
    "limits": {
      "max_results": 5
    }
  }'
```

### Output

Each run prints:

- the final request payload sent to `POST /api/search`
- the accepted kickoff response, including `snapshot_url` and `events_url`
- streamed SSE events unless `--no-stream` is set
- the final job snapshot and a compact result list
- synthetic TinyFish heartbeat events during long scrapes so the stream does not go quiet

### Flag Reference

- `query_text`: positional plain-text query. Ignored when `--payload-json` or
  `--payload-file` is present.
- `--base-url`: backend base URL. Defaults to `http://localhost:8000`.
- `--payload-json`: full `POST /api/search` body as inline JSON.
- `--payload-file`: path to a JSON file containing the full
  `POST /api/search` body.
- `--profile-json`: JSON object merged into `query.profile` when using
  positional `query_text`.
- `--stream-tinyfish`: set `stream_tinyfish=true` in the request body. This is
  enabled by default.
- `--no-stream-tinyfish`: set `stream_tinyfish=false` in the request body.
- `--max-depth`: override `limits.max_depth`.
- `--max-subexplorers`: override `limits.max_subexplorers`.
- `--max-results`: override `limits.max_results`.
- `--seed-limit`: override `limits.seed_limit`.
- `--domain-limit`: override `limits.domain_limit`.
- `--no-stream`: skip the SSE event stream entirely and fetch only the final
  snapshot once.
- `--show-keepalive`: print keepalive SSE frames. By default they are hidden.
- `--raw-events`: print full parsed SSE event payloads instead of the condensed
  event summary.
- `--timeout`: per-request HTTP timeout in seconds. Defaults to `120`.

### Important Behaviors

- Use either `--payload-json` or `--payload-file`, not both.
- If neither payload flag is passed, `query_text` is required.
- `--profile-json` must decode to a JSON object.
- Any limit flags passed on the command line override the corresponding values
  inside the payload.
- The CLI always injects `stream_tinyfish` into the final request payload based
  on `--stream-tinyfish` or `--no-stream-tinyfish`.

### Handy Combinations

Fetch the final snapshot only, without SSE noise:

```bash
uv run python scripts/search_cli.py "embroidered denim underground brands" \
  --base-url http://localhost:8000 \
  --profile-json '{"style":["avant-garde","DIY"]}' \
  --no-stream
```

Inspect raw event payloads while keeping the stream enabled:

```bash
uv run python scripts/search_cli.py "embroidered denim underground brands" \
  --base-url http://localhost:8000 \
  --raw-events \
  --show-keepalive
```
