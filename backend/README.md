# Backend

FastAPI backend with [Restate](https://restate.dev/) for durable execution.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Restate server: `brew install restatedev/tap/restate-server`

## Setup

Install dependencies:

```
uv sync
```

## Running

1. Start the Restate server:

```
restate-server
```

2. Start the FastAPI backend (in a separate terminal):

```
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

3. Register the backend with Restate:

```
curl http://localhost:9070/deployments -H 'content-type: application/json' \
  -d '{"uri": "http://localhost:8000/restate", "use_http_11": true}'
```

4. Test the greeter service:

```
curl http://localhost:8080/Greeter/greet -H 'content-type: application/json' -d '"world"'
```
