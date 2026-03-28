"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

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

const streamedWebsites = [
  {
    id: "atlas",
    name: "Atlas Obscura",
    href: "https://www.atlasobscura.com",
    blurb: "A rich source of unusual destinations, hidden landmarks, and local curiosities.",
    progress: 23,
    circleX: 27,
    circleY: 23.6,
    popupSide: "right",
    islandStyle: "lagoon",
  },
  {
    id: "compass",
    name: "Hidden Compass",
    href: "https://hiddencompass.net",
    blurb: "Travel storytelling with a strong secret-paths energy that fits the product well.",
    progress: 67,
    circleX: 74.7,
    circleY: 37.1,
    popupSide: "left",
    islandStyle: "cliff",
  },
  {
    id: "roads",
    name: "Roads & Kingdoms",
    href: "https://roadsandkingdoms.com",
    blurb: "Useful for discovery through food, neighborhoods, and distinctive local culture.",
    progress: 47,
    circleX: 40.4,
    circleY: 58,
    popupSide: "right",
    islandStyle: "volcano",
  },
  {
    id: "locals",
    name: "Spotted by Locals",
    href: "https://www.spottedbylocals.com",
    blurb: "A strong mock example of city-based hidden gems recommended by local voices.",
    progress: 88,
    circleX: 81.9,
    circleY: 84.6,
    popupSide: "left",
    islandStyle: "grove",
  },
];

const curatedWebsites = [
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

export default function ExploringPage() {
  const curatedSectionRef = useRef<HTMLElement | null>(null);
  const [activeIsland, setActiveIsland] = useState<string | null>(null);
  const [fishFacing, setFishFacing] = useState<"forward" | "backward">("forward");
  const [showCurated, setShowCurated] = useState(false);
  const [fishDock, setFishDock] = useState<{ top: string; left: string }>({
    top: "14%",
    left: "7%",
  });

  const selectedWebsite =
    streamedWebsites.find((website) => website.id === activeIsland) ?? null;

  useEffect(() => {
    if (!showCurated) {
      return;
    }

    curatedSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [showCurated]);

  const scrollToCurated = () => {
    setShowCurated(true);
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
    const destination = streamedWebsites.find((website) => website.id === islandId);

    if (!destination) {
      return;
    }

    const currentIsland = streamedWebsites.find((website) => website.id === activeIsland);
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
              Each island is a streamed website. Click one to inspect the link,
              then tap the treasure marker to jump down to the curated shortlist.
            </p>
          </div>
        </div>

        <div className="map-board">
          <svg
            className="map-paths"
            viewBox="0 0 1000 700"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d={MAP_ROUTE_PATH}
              className="map-route map-route-pink"
            />
            <path
              d={MAP_ROUTE_PATH}
              className="map-route map-route-white-soft"
            />
            <circle cx="88" cy="126" r="11" className="route-stop route-start" />
            {streamedWebsites.map((website) => (
              <circle
                key={website.id}
                cx={website.circleX * 10}
                cy={website.circleY * 7}
                r="10"
                className="route-stop"
              />
            ))}
            <circle cx="642" cy="684" r="12" className="route-stop route-stop-final" />
          </svg>

          <button
            type="button"
            className="map-start-button"
            onClick={moveFishToStart}
            aria-label="Return to start"
          >
            Start
          </button>

          <div
            className="map-fish"
            style={{
              top: fishDock.top,
              left: fishDock.left,
            }}
          >
            <Image
              src="/fische-fish.png"
              alt="fische explorer fish"
              width={128}
              height={128}
              className={`map-fish-image map-fish-image-${fishFacing}`}
              priority
            />
          </div>

          {streamedWebsites.map((website) => (
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

          <button type="button" className="treasure-marker" onClick={scrollToCurated}>
            <span className="treasure-x">X</span>
            <span className="treasure-kicker">Curated drop</span>
            <span className="treasure-label">Final destination</span>
          </button>
        </div>
      </section>

      {showCurated ? (
        <section className="curated-shell" ref={curatedSectionRef}>
          <div className="curated-heading">
            <span className="hero-badge">curated shortlist</span>
            <h2>Treasure island</h2>
            <p>
              This section can later be filled with your backend’s final curated
              websites. For now, I’ve added mock entries so the interaction works.
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
        </section>
      ) : null}
    </main>
  );
}
