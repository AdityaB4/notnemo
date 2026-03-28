# AGENTS.md

## Project

Build a niche result finder engine that returns genuinely specific, high-signal results instead of generic SEO-shaped recommendations.

Primary use cases:
- "Find me a Japanese restaurant"
- "Find me niche music similar to Deftones"
- Any natural-language query where existing LLM assistants tend to return broad, obvious, over-exposed answers

The product should feel like a discovery engine with taste, not a generic search box.

## Mission

Users should be able to:
- Describe what they want in natural language
- Build a richer taste/profile signal through onboarding
- Receive niche, high-relevance results backed by crawled and freshly-scraped data

The system must optimize for:
- specificity over popularity
- freshness over static stale lists
- taste alignment over generic relevance
- speed fast enough for interactive search

## Core Domains

The project has three core domains:

1. Frontend
   Own the ocean-themed web experience, natural-language query flow, onboarding, and results presentation.

2. Backend Search + Ranking
   Own ingestion-facing APIs, query parsing, retrieval, ranking, personalization, and real-time augmentation.

3. Crawling + Data Collection
   Own TinyFish-powered crawling, extraction, normalization, enrichment, and source freshness.

## Agent Roster

### 1. Product / Orchestrator Agent

Purpose:
- Maintain shared direction across all domains
- Define milestones, interfaces, and acceptance criteria
- Prevent the team from building disconnected components

Owns:
- product scope
- end-to-end user journey
- shared schemas and contracts
- demo readiness

Responsibilities:
- Keep the frontend, backend, and crawler aligned on one search loop
- Define what a "good result" means
- Resolve ambiguous scope quickly in favor of shipping
- Track blockers and push teams toward thin vertical slices

Deliverables:
- shared roadmap
- domain contracts
- demo script
- success metrics for the hackathon build

### 2. Frontend Agent

Purpose:
- Build a beautiful ocean-themed webapp that makes discovery feel premium, intentional, and alive

Owns:
- landing/search page
- onboarding flow
- query input UX
- results UI
- loading, empty, and error states
- profile editing UI

Responsibilities:
- Accept natural-language queries
- Collect onboarding inputs that improve personalization
- Present why each result matches the user
- Expose freshness and niche signals in the UI
- Keep interaction fast, clear, and mobile-friendly

Expected features:
- immersive ocean-themed visual design
- animated onboarding flow
- search input with example prompts
- result cards with tags, explanations, and source links
- saved preferences/profile summary

Outputs to backend:
- raw query text
- structured profile preferences
- interaction feedback signals such as clicks, saves, skips, likes

Dependencies:
- search API
- profile API
- ranking explanations

### 3. Backend Search Agent

Purpose:
- Turn user intent plus profile data into fast, high-quality, niche-first results

Owns:
- search API
- profile API
- ranking pipeline
- retrieval orchestration
- personalization logic
- real-time scraping triggers

Responsibilities:
- Parse natural-language queries into retrievable intent
- Search across crawled/indexed data
- Fuse profile data into retrieval and ranking
- Trigger targeted real-time scraping when coverage is weak
- Return structured explanations for each result

Core capabilities:
- hybrid retrieval over crawled data
- personalization weighting
- novelty / niche score
- freshness score
- confidence score
- deduplication and source consolidation

Suggested endpoints:
- `POST /api/search`
- `POST /api/profile`
- `GET /api/profile/:id`
- `POST /api/feedback`
- `POST /api/enrich`

Return shape for search:
- result id
- title
- description
- category
- source url
- tags
- why it matched
- freshness
- niche score
- confidence

### 4. Crawling + Data Agent

Purpose:
- Build and maintain the data advantage using TinyFish plus targeted enrichment

Owns:
- crawler definitions
- source selection
- extraction rules
- normalization pipelines
- freshness tracking
- enrichment jobs

Responsibilities:
- Crawl relevant sources using TinyFish
- Extract structured entities from messy web data
- Normalize places, artists, genres, scenes, locations, and attributes
- Keep provenance for every record
- Identify when search gaps require additional crawling or live scraping

Data priorities:
- non-obvious sources
- community-driven sources
- local or niche publications
- independent blogs and forums
- structured metadata whenever possible

Artifacts:
- raw crawl output
- normalized entities
- searchable index documents
- source metadata
- freshness timestamps

## Shared Product Principles

All agents must optimize for these principles:

- Niche-first: prefer depth and specificity over mainstream popularity
- Explainability: every result should have a clear reason it appeared
- Freshness: recent and actively maintained sources should surface when relevant
- Taste-awareness: user profile should materially improve relevance
- Speed: first meaningful results should appear quickly
- Source transparency: users should be able to inspect where results came from

## Shared Contracts

### Query Contract

Frontend sends:
- query text
- user id or anonymous session id
- selected onboarding/profile fields
- optional context such as location, mood, budget, genre, or intent

Backend returns:
- ranked results
- result explanations
- optional follow-up filters
- confidence / coverage indicators

### Profile Contract

Profile fields can include:
- location
- cuisines or scenes of interest
- price sensitivity
- adventurousness / niche tolerance
- favorite artists, genres, venues, or aesthetics
- disliked categories
- preferred distance / travel tolerance

### Data Contract

Crawler output should normalize into records with:
- entity type
- title / name
- summary
- tags
- location if relevant
- source url
- source type
- crawl timestamp
- freshness signal
- extraction confidence

## Build Order

Ship as thin vertical slices:

1. Search box + mock onboarding + stubbed results
2. Real backend endpoint returning ranked sample data
3. TinyFish crawler producing normalized records
4. Indexed retrieval over crawled data
5. Personalized ranking using onboarding data
6. Real-time scraping fallback for sparse queries
7. Polish, performance, and demo flow

## Definition of Done

The hackathon build is successful when:
- a user can complete onboarding
- a user can enter a natural-language query
- the backend returns niche, explainable results
- at least part of the result set comes from TinyFish-crawled data
- the UI clearly communicates why results are relevant
- the full flow is stable enough for a live demo

## Non-Goals For V1

Avoid spending hackathon time on:
- full auth and account management
- enterprise-grade infra
- massive source coverage
- perfect ranking science
- overly complex agent orchestration

Prefer a convincing end-to-end demo over broad but shallow functionality.

## Operating Rules

- Build vertical slices, not isolated subsystems
- Default to shipping the smallest testable version
- Keep all interfaces explicit and documented
- Preserve source attribution from crawl to result
- Do not let beautiful UI hide weak relevance
- Do not let backend complexity delay a demoable experience

## Suggested Folder Ownership

If the repo is structured from scratch, a clean split is:

- `apps/web` for frontend
- `apps/api` for backend
- `apps/crawler` or `services/crawler` for TinyFish crawling
- `packages/types` for shared schemas
- `packages/ui` for reusable UI primitives if needed

## Immediate Next Tasks

1. Define the shared search result schema
2. Choose the frontend stack and scaffold the ocean-themed UI
3. Stand up a minimal search API with mocked results
4. Configure the first TinyFish crawl targets
5. Connect one complete end-to-end demo query flow
