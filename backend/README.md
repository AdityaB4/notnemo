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

```
docker run --name restate_dev --rm -p 8080:8080 -p 9070:9070 -p 9071:9071 docker.io/restatedev/restate:latest
```
3. Register the backend with Restate:

```
curl http://localhost:9070/deployments -H 'content-type: application/json' \
  -d '{"uri": "http://localhost:8000/restate", "use_http_11": true}'
```

If using docker to run restate:
```
curl http://localhost:9070/deployments \
  -H 'content-type: application/json' \
  -d '{"uri": "http://host.docker.internal:8000/restate", "use_http_11": true}'
```

4. Test the greeter service:

```
curl http://localhost:8080/Greeter/greet -H 'content-type: application/json' -d '"world"'
```
