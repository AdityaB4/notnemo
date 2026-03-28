"use client";

import Image from "next/image";
import { useRef, useState } from "react";

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

const streamedWebsites = [
  {
    id: "atlas",
    name: "Atlas Obscura",
    href: "https://www.atlasobscura.com",
    blurb: "A rich source of unusual destinations, hidden landmarks, and local curiosities.",
    top: "19%",
    left: "24%",
    shape: "ring",
  },
  {
    id: "compass",
    name: "Hidden Compass",
    href: "https://hiddencompass.net",
    blurb: "Travel storytelling with a strong secret-paths energy that fits the product well.",
    top: "33%",
    left: "58%",
    shape: "square",
  },
  {
    id: "roads",
    name: "Roads & Kingdoms",
    href: "https://roadsandkingdoms.com",
    blurb: "Useful for discovery through food, neighborhoods, and distinctive local culture.",
    top: "57%",
    left: "38%",
    shape: "triangle",
  },
  {
    id: "locals",
    name: "Spotted by Locals",
    href: "https://www.spottedbylocals.com",
    blurb: "A strong mock example of city-based hidden gems recommended by local voices.",
    top: "66%",
    left: "76%",
    shape: "oval",
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
  const [activeIsland, setActiveIsland] = useState<string>(streamedWebsites[1].id);

  const selectedWebsite =
    streamedWebsites.find((website) => website.id === activeIsland) ?? streamedWebsites[0];

  const scrollToCurated = () => {
    curatedSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
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
              d="M114 144C193 129 229 210 286 226C356 247 373 147 470 159C574 171 593 262 664 275C732 287 791 245 824 202"
              className="map-route map-route-pink"
            />
            <path
              d="M662 324C667 385 727 423 806 442"
              className="map-route map-route-pink"
            />
            <path
              d="M808 482C746 503 696 523 631 559"
              className="map-route map-route-white"
            />
          </svg>

          <div className="map-fish">
            <Image
              src="/fische-fish.png"
              alt="fische explorer fish"
              width={128}
              height={128}
              className="map-fish-image"
              priority
            />
          </div>

          {streamedWebsites.map((website) => (
            <button
              key={website.id}
              type="button"
              className={`map-island island-${website.shape} ${
                activeIsland === website.id ? "island-active" : ""
              }`}
              style={{ top: website.top, left: website.left }}
              onClick={() => setActiveIsland(website.id)}
            >
              <span className="sr-only">{website.name}</span>
            </button>
          ))}

          <div className="island-popover">
            <p className="island-popover-label">Website link</p>
            <strong>{selectedWebsite.name}</strong>
            <a href={selectedWebsite.href} target="_blank" rel="noreferrer">
              {selectedWebsite.href}
            </a>
            <p>{selectedWebsite.blurb}</p>
          </div>

          <button type="button" className="treasure-marker" onClick={scrollToCurated}>
            <span className="treasure-x">X</span>
            <span className="treasure-label">Final destination</span>
          </button>
        </div>
      </section>

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
    </main>
  );
}
