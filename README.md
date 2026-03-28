# NotNemo (Fische)

A niche search and discovery engine that returns genuinely specific, high-signal results instead of generic SEO-shaped recommendations. Ask natural-language queries like _"Find me underground embroidered denim brands"_ and get curated, explainable results from across the web.

## Tech Stack

- **Frontend:** Next.js 14, React 18, TypeScript
- **Backend:** Python 3.11+, FastAPI, Restate SDK (durable workflows)
- **Database:** PostgreSQL + pgvector (embeddings & caching)
- **AI:** OpenAI (search reasoning & embeddings)
- **Crawling:** TinyFish API (fresh, niche data)
- **Infra:** Docker, Fly.io

## Getting Started

### Prerequisites

- Node.js
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- PostgreSQL (optional — caching/embeddings disabled without it)

### Environment Variables

Create `backend/.env.local`:

```bash
OPENAI_API_KEY=...
TINYFISH_API_KEY=...
# Optional
DATABASE_URL=...
RESTATE_INGRESS_URL=http://localhost:8080
RESTATE_ADMIN_URL=http://localhost:9070
BRAINTRUST_API_KEY=...
```

### Run

```bash
# Setup
./scripts/setup.sh

# Backend (terminal 1)
cd backend
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`, backend on `http://localhost:8000`.

## Project Structure

```
├── frontend/          # Next.js app
│   ├── app/
│   │   ├── page.tsx           # Onboarding (taste profile)
│   │   ├── explore/           # Search input
│   │   └── exploring/         # Interactive journey map & results
│   └── ...
├── backend/           # FastAPI + Restate
│   ├── backend/
│   │   ├── app.py             # FastAPI setup
│   │   ├── routes.py          # API endpoints
│   │   ├── restate_services.py # Durable search workflows
│   │   ├── db.py              # PostgreSQL + pgvector
│   │   ├── openai_explorer.py # Search reasoning
│   │   └── tinyfish.py        # Web crawling
│   └── ...
├── infra/             # Fly.io configs (db, restate)
└── scripts/           # Setup & run helpers
```

## How It Works

1. User submits a natural-language query with optional taste profile
2. Backend normalizes the query and checks the embedding cache
3. On cache miss, a Restate workflow orchestrates the search:
   - OpenAI reasons about query intent
   - Web search seeds initial results
   - Branching sub-explorers dive deeper into niches
   - TinyFish scrapes fresh, community-driven sources
4. Results stream to the frontend via SSE as they're discovered
5. Frontend renders an interactive journey map with the fish mascot navigating to "islands" (results)

## API

| Endpoint | Description |
|---|---|
| `POST /api/search` | Create a search job |
| `GET /api/search/{job_id}` | Fetch search snapshot |
| `GET /api/search/{job_id}/events` | SSE stream of results |
| `GET /health` | Health check |

## Testing

```bash
# Backend unit tests
cd backend
RESTATE_AUTO_REGISTER=false uv run python -m unittest discover -s tests -v

# Manual CLI search
uv run python scripts/search_cli.py "japanese restaurants in toronto" --base-url http://localhost:8000
```
