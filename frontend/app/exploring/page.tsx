"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useSearchParams } from "next/navigation";

import { getApiBaseUrl } from "../lib/api";
import { readSearchSession, writeSearchSession } from "../lib/search-session";

const bubbles = [
  { left: "6%", size: 18, duration: 12, delay: 0 },
  { left: "14%", size: 12, duration: 16, delay: 4 },
  { left: "23%", size: 24, duration: 11, delay: 1 },
  { left: "37%", size: 14, duration: 15, delay: 6 },
  { left: "49%", size: 20, duration: 13, delay: 3 },
  { left: "61%", size: 16, duration: 17, delay: 5 },
  { left: "74%", size: 26, duration: 12, delay: 2 },
  { left: "88%", size: 10, duration: 14, delay: 7 },
];

const MAP_ROUTE_PATH =
  "M88 126C156 92 230 104 274 152C311 193 314 250 301 291C286 338 302 379 351 403C406 430 485 411 564 354C627 308 683 256 750 260C821 264 876 322 893 392C911 462 884 544 823 601C780 641 721 668 642 684";

const ROUTE_SEGMENTS = [
  "M88 126C146 104 215 112 270 165",
  "M270 165C321 214 316 319 404 406",
  "M404 406C495 442 621 302 747 259",
  "M747 259C842 264 899 498 819 592",
  "M819 592C780 650 711 671 642 684",
] as const;

const islandStyles = ["lagoon", "cliff", "volcano", "grove"] as const;

type ApiSearchResult = {
  result_id: string;
  url: string;
  description: string;
  source_kind: string;
  why_matched: string;
  tags?: string[];
  confidence: number;
  branch_id: string;
};

type ApiSearchSnapshot = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  results: ApiSearchResult[];
  errors: Array<{ message: string }>;
};

type MapIsland = {
  id: string;
  name: string;
  href: string;
  blurb: string;
  progress: number;
  circleX: number;
  circleY: number;
  popupSide: "left" | "right";
  islandStyle: (typeof islandStyles)[number];
};

const fallbackCuratedWebsites = [
  {
    name: "Atlas Obscura",
    href: "https://www.atlasobscura.com",
    reason: "Great for weird landmarks, hidden restaurants, and offbeat itineraries.",
  },
  {
    name: "Roads & Kingdoms",
    href: "https://roadsandkingdoms.com",
    reason: "Editorially strong for place, culture, and destination-specific food discoveries.",
  },
  {
    name: "Spotted by Locals",
    href: "https://www.spottedbylocals.com",
    reason: "Feels close to your product’s promise of personal, niche, city-level recommendations.",
  },
];

function resultName(url: string): string {
  try {
    const hostname = new URL(url).hostname.replace(/^www\./, "");
    const root = hostname.split(".")[0] ?? hostname;
    return root
      .split(/[-_]/g)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  } catch {
    return "Website";
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function toMapIslands(results: ApiSearchResult[]): MapIsland[] {
  if (results.length === 0) {
    return [];
  }

  const routeProgresses = [23, 47, 67, 88];
  const circleXs = [27, 40.4, 74.7, 81.9];
  const circleYs = [23.6, 58, 37.1, 84.6];

  return results.slice(0, 4).map((result, index) => {
    const progress = routeProgresses[index] ?? clamp(18 + index * 16, 18, 88);
    const circleX = circleXs[index] ?? clamp(24 + index * 15, 18, 84);
    const circleY = circleYs[index] ?? clamp(22 + index * 12, 20, 84);

    return {
      id: result.result_id || `${result.url}-${index}`,
      name: resultName(result.url),
      href: result.url,
      blurb: result.description || result.why_matched || "Freshly discovered by the backend search stream.",
      progress,
      circleX,
      circleY,
      popupSide: circleX > 56 ? "left" : "right",
      islandStyle: islandStyles[index % islandStyles.length],
    };
  });
}

export default function ExploringPage() {
  const searchParams = useSearchParams();
  const curatedSectionRef = useRef<HTMLElement | null>(null);
  const startedRef = useRef(false);

  const [activeIsland, setActiveIsland] = useState<string | null>(null);
  const [fishFacing, setFishFacing] = useState<"forward" | "backward">("forward");
  const [showCurated, setShowCurated] = useState(false);
  const [isRevealingCurated, setIsRevealingCurated] = useState(false);
  const [fishDock, setFishDock] = useState<{ top: string; left: string }>({
    top: "14%",
    left: "7%",
  });
  const [jobStatus, setJobStatus] = useState<"idle" | "loading" | "running" | "completed" | "failed">("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [streamedResults, setStreamedResults] = useState<ApiSearchResult[]>([]);

  const session = useMemo(() => readSearchSession(), []);
  const exploreQuery = searchParams.get("query")?.trim() || session.explore.trim();
  const aboutText = session.about.trim();

  const islands = useMemo(() => toMapIslands(streamedResults), [streamedResults]);
  const curatedWebsites = useMemo(() => {
    if (streamedResults.length === 0) {
      return fallbackCuratedWebsites;
    }

    return streamedResults.slice(0, 6).map((result) => ({
      name: resultName(result.url),
      href: result.url,
      reason: result.description || result.why_matched || "Selected from the backend search results.",
    }));
  }, [streamedResults]);

  const latestResult = streamedResults[streamedResults.length - 1] ?? null;
  const visibleSegments = jobStatus === "completed" ? islands.length + 1 : islands.length;

  const selectedWebsite = islands.find((website) => website.id === activeIsland) ?? null;

  useEffect(() => {
    if (!showCurated) {
      return;
    }

    curatedSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [showCurated]);

  useEffect(() => {
    if (!isRevealingCurated) {
      return;
    }

    const revealTimer = window.setTimeout(() => {
      setShowCurated(true);
      setIsRevealingCurated(false);
    }, 1350);

    return () => window.clearTimeout(revealTimer);
  }, [isRevealingCurated]);

  useEffect(() => {
    if (startedRef.current) {
      return;
    }

    if (!exploreQuery) {
      setJobError("Add a place to explore first so we can start the search.");
      setJobStatus("failed");
      startedRef.current = true;
      return;
    }

    startedRef.current = true;
    writeSearchSession({ explore: exploreQuery });

    const controller = new AbortController();
    const apiBase = getApiBaseUrl();
    let eventSource: EventSource | null = null;

    async function startSearch() {
      try {
        setJobStatus("loading");
        setJobError(null);

        const response = await fetch(`${apiBase}/api/search`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: {
              text: exploreQuery,
              profile: aboutText ? { preferences: aboutText } : {},
            },
            limits: {
              max_results: 10,
            },
            stream_tinyfish: true,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Search request failed with ${response.status}.`);
        }

        const accepted = (await response.json()) as {
          job_id: string;
          snapshot_url: string;
          events_url: string;
        };

        setJobId(accepted.job_id);
        setJobStatus("running");

        eventSource = new EventSource(`${apiBase}${accepted.events_url}`);
        eventSource.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data) as {
              event_type: string;
              payload: { result?: ApiSearchResult };
            };

            if (parsed.event_type === "result.item" && parsed.payload?.result) {
              setStreamedResults((current) => {
                const next = [...current];
                const existingIndex = next.findIndex(
                  (item) => item.result_id === parsed.payload.result?.result_id,
                );

                if (existingIndex >= 0) {
                  next[existingIndex] = parsed.payload.result;
                } else {
                  next.push(parsed.payload.result);
                }

                return next;
              });
            }

            if (parsed.event_type === "job.completed") {
              setJobStatus("completed");
              eventSource?.close();
            }

            if (parsed.event_type === "job.failed") {
              setJobStatus("failed");
              setJobError("The backend search failed before finishing.");
              eventSource?.close();
            }
          } catch {
            // Ignore malformed event frames.
          }
        };

        eventSource.onerror = async () => {
          eventSource?.close();
          try {
            const snapshotResponse = await fetch(`${apiBase}${accepted.snapshot_url}`, {
              signal: controller.signal,
            });

            if (!snapshotResponse.ok) {
              throw new Error("Snapshot fallback failed.");
            }

            const snapshot = (await snapshotResponse.json()) as ApiSearchSnapshot;
            setStreamedResults(snapshot.results ?? []);
            setJobStatus(snapshot.status === "failed" ? "failed" : snapshot.status === "completed" ? "completed" : "running");
            if (snapshot.status === "failed") {
              setJobError(snapshot.errors?.[0]?.message ?? "The backend search failed.");
            }
          } catch {
            setJobStatus("failed");
            setJobError("Could not connect to the backend event stream.");
          }
        };
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        setJobStatus("failed");
        setJobError(error instanceof Error ? error.message : "Could not start the backend search.");
      }
    }

    startSearch();

    return () => {
      controller.abort();
      eventSource?.close();
    };
  }, [aboutText, exploreQuery]);

  const scrollToCurated = () => {
    if (showCurated || isRevealingCurated) {
      setShowCurated(true);
      return;
    }

    setIsRevealingCurated(true);
  };

  const moveFishToStart = () => {
    setFishFacing("backward");
    setFishDock({
      top: "14%",
      left: "7%",
    });
    setActiveIsland(null);
  };

  const moveFishToIsland = (islandId: string) => {
    const destination = islands.find((website) => website.id === islandId);

    if (!destination) {
      return;
    }

    const currentIsland = islands.find((website) => website.id === activeIsland);
    const currentProgress = currentIsland?.progress ?? 0;

    if (destination.progress < currentProgress) {
      setFishFacing("backward");
    } else if (destination.progress > currentProgress) {
      setFishFacing("forward");
    }

    const islandTop = destination.circleY - 8.5;
    const islandLeft = destination.circleX;

    setFishDock({
      top: `${islandTop + 2}%`,
      left: `${islandLeft - 7}%`,
    });
    setActiveIsland(islandId);
  };

  return (
    <main className="intro-page exploring-page">
      <div className="water-glow water-glow-top" />
      <div className="water-glow water-glow-middle" />
      <div className="water-glow water-glow-bottom" />

      <div className="bubbles" aria-hidden="true">
        {bubbles.map((bubble) => (
          <span
            key={`${bubble.left}-${bubble.delay}`}
            className="bubble"
            style={{
              left: bubble.left,
              width: `${bubble.size}px`,
              height: `${bubble.size}px`,
              animationDuration: `${bubble.duration}s`,
              animationDelay: `${bubble.delay}s`,
            }}
          />
        ))}
      </div>

      <section className="map-shell">
        <div className="map-header">
          <span className="hero-badge">fische journey map</span>
          <div className="map-copy">
            <h1>Exploring the web for niche gems</h1>
            <p>
              {exploreQuery
                ? `Searching for ${exploreQuery}. Click a discovered island to inspect the link, then tap the treasure marker to reveal the shortlist.`
                : "Click a discovered island to inspect the link, then tap the treasure marker to reveal the shortlist."}
            </p>
            {latestResult ? (
              <p className="map-activity">
                TinyFish is now checking <strong>{resultName(latestResult.url)}</strong>.
              </p>
            ) : null}
          </div>
          <div className="exploring-status">
            <span className={`status-pill status-pill-${jobStatus}`}>{jobStatus}</span>
            {jobId ? <span className="status-meta">Job {jobId}</span> : null}
            {jobError ? <span className="status-error">{jobError}</span> : null}
          </div>
        </div>

        <div className="map-board">
          <svg className="map-paths" viewBox="0 0 1000 700" preserveAspectRatio="none" aria-hidden="true">
            {ROUTE_SEGMENTS.slice(0, visibleSegments).map((segment, index) => (
              <g key={segment}>
                <path d={segment} className="map-route map-route-white-soft" />
                <path d={segment} className="map-route map-route-pink" />
              </g>
            ))}
            <circle cx="88" cy="126" r="11" className="route-stop route-start" />
            {islands.map((website) => (
              <circle
                key={website.id}
                cx={website.circleX * 10}
                cy={website.circleY * 7}
                r="10"
                className="route-stop"
              />
            ))}
            {jobStatus === "completed" ? (
              <circle cx="642" cy="684" r="12" className="route-stop route-stop-final" />
            ) : null}
          </svg>

          <button type="button" className="map-start-button" onClick={moveFishToStart} aria-label="Return to start">
            Start
          </button>

          <div className="map-fish" style={{ top: fishDock.top, left: fishDock.left }}>
            <Image
              src="/fische-fish.png"
              alt="fische explorer fish"
              width={128}
              height={128}
              className={`map-fish-image map-fish-image-${fishFacing}`}
              priority
            />
          </div>

          {islands.length === 0 ? (
            <div className="map-empty-state">
              {jobStatus === "failed"
                ? "The backend search did not return islands yet."
                : "Waiting for the backend to stream website islands..."}
            </div>
          ) : null}

          {islands.map((website) => (
            <button
              key={website.id}
              type="button"
              className={`map-island ${activeIsland === website.id ? "island-active" : ""}`}
              style={{
                top: `${website.circleY - 8.5}%`,
                left: `${website.circleX}%`,
              }}
              onClick={() => moveFishToIsland(website.id)}
            >
              <span className={`island-art island-art-${website.islandStyle}`} aria-hidden="true">
                <span className="island-shadow" />
                <span className="island-sand" />
                <span className="island-grass" />
                <span className="island-detail island-detail-a" />
                <span className="island-detail island-detail-b" />
                <span className="island-detail island-detail-c" />
                <span className="island-detail island-detail-d" />
              </span>
              <span className="island-name">{website.name}</span>
              <span className="sr-only">{website.name}</span>
            </button>
          ))}

          {selectedWebsite ? (
            <div
              className={`island-popover island-popover-${selectedWebsite.popupSide}`}
              style={{
                top: `${selectedWebsite.circleY - 4}%`,
                left: `${selectedWebsite.circleX + (selectedWebsite.popupSide === "right" ? 20 : -20)}%`,
              }}
            >
              <p className="island-popover-label">Website link</p>
              <strong>{selectedWebsite.name}</strong>
              <a href={selectedWebsite.href} target="_blank" rel="noreferrer">
                {selectedWebsite.href}
              </a>
              <p>{selectedWebsite.blurb}</p>
            </div>
          ) : null}

          {jobStatus === "completed" ? (
            <button type="button" className="treasure-marker" onClick={scrollToCurated}>
              <span className="treasure-x">X</span>
              <span className="treasure-kicker">Curated drop</span>
              <span className="treasure-label">Final destination</span>
            </button>
          ) : null}

          {isRevealingCurated ? (
            <div className="curated-reveal" aria-hidden="true">
              <div className="curated-reveal-haze" />
              {Array.from({ length: 84 }).map((_, index) => (
                <span
                  key={index}
                  className="curated-reveal-bubble"
                  style={
                    {
                      left: `${(index * 19) % 100}%`,
                      bottom: `${-10 + ((index * 11) % 24)}%`,
                      width: `${42 + (index % 8) * 22}px`,
                      height: `${42 + (index % 8) * 22}px`,
                      animationDelay: `${(index % 10) * 55}ms`,
                      animationDuration: `${1050 + (index % 6) * 140}ms`,
                    } as CSSProperties
                  }
                />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      {showCurated ? (
        <section className="curated-shell" ref={curatedSectionRef}>
          <div className="curated-heading">
            <span className="hero-badge">curated shortlist</span>
            <h2>Treasure island</h2>
            <p>
              {jobStatus === "completed"
                ? "These cards are now coming from the backend search results."
                : "If the backend is still working, this shortlist will fill in with the latest results we already have."}
            </p>
          </div>

          <div className="curated-grid">
            {curatedWebsites.map((website) => (
              <article className="curated-card" key={website.href}>
                <h3>{website.name}</h3>
                <a href={website.href} target="_blank" rel="noreferrer">
                  {website.href}
                </a>
                <p>{website.reason}</p>
              </article>
            ))}
          </div>

          <div className="curated-cta">
            <p>Want to explore again?</p>
            <Link className="curated-cta-button" href="/explore">
              Explore another place
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
