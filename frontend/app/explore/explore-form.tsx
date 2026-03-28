"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { readSearchSession, writeSearchSession } from "../lib/search-session";

export function ExploreForm() {
  const [explore, setExplore] = useState("");

  useEffect(() => {
    setExplore(readSearchSession().explore);
  }, []);

  const href = useMemo(() => {
    const query = explore.trim();
    return query.length > 0
      ? `/exploring?query=${encodeURIComponent(query)}`
      : "/exploring";
  }, [explore]);

  return (
    <div className="explore-card">
      <p className="explore-kicker">Next stop</p>
      <h1>Where would you like to explore?</h1>

      <div className="explore-input-row">
        <input
          id="explore-location"
          className="explore-input"
          type="text"
          placeholder="Singapore, Kyoto, hidden streets in Seoul..."
          value={explore}
          onChange={(event) => setExplore(event.target.value)}
        />

        <Link
          className="explore-button"
          href={href}
          aria-label="Continue"
          onClick={() => {
            writeSearchSession({ explore });
          }}
        >
          Go
        </Link>
      </div>

      <p className="explore-helper">
        Pick a city, neighborhood, or even a vibe. We&apos;ll take it from there.
      </p>
    </div>
  );
}
