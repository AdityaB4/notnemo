"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { readSearchSession, writeSearchSession } from "./lib/search-session";

const starterTags = [
  "Hidden food spots",
  "Quiet anniversary plans",
  "Indie coffee places",
  "Artsy neighborhoods",
];

export function IntroForm() {
  const [about, setAbout] = useState("");

  useEffect(() => {
    setAbout(readSearchSession().about);
  }, []);

  return (
    <form className="intake-card">
      <label className="intake-label" htmlFor="about-you">
        What should we know about you?
      </label>
      <textarea
        id="about-you"
        className="response-input"
        placeholder="I love cozy places, seafood, slow evenings, handmade things, and anywhere that feels like a secret."
        rows={5}
        value={about}
        onChange={(event) => setAbout(event.target.value)}
      />

      <div className="tag-row" aria-label="Sample preferences">
        {starterTags.map((tag) => (
          <button
            key={tag}
            type="button"
            className="tag-chip tag-chip-button"
            onClick={() => {
              setAbout((current) => {
                if (current.includes(tag)) {
                  return current;
                }
                const next = current.trim().length > 0 ? `${current.trim()}, ${tag}` : tag;
                return next;
              });
            }}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="card-footer">
        <p className="helper-text">
          This helps fische tune future searches to your vibe.
        </p>
        <Link
          className="continue-button"
          href="/explore"
          onClick={() => {
            writeSearchSession({ about });
          }}
        >
          Start exploring
        </Link>
      </div>
    </form>
  );
}
