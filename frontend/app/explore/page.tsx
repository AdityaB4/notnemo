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

export default function ExplorePage() {
  return (
    <main className="intro-page explore-page">
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

      <section className="explore-shell">
        <span className="hero-badge">fische destination</span>

        <div className="explore-card">
          <p className="explore-kicker">Next stop</p>
          <h1>Where would you like to explore?</h1>

          <label className="sr-only" htmlFor="explore-location">
            Where would you like to explore?
          </label>

          <div className="explore-input-row">
            <input
              id="explore-location"
              className="explore-input"
              type="text"
              placeholder="Singapore, Kyoto, hidden streets in Seoul..."
            />

            <button className="explore-button" type="button" aria-label="Continue">
              Go
            </button>
          </div>

          <p className="explore-helper">
            Pick a city, neighborhood, or even a vibe. We&apos;ll take it from there.
          </p>
        </div>
      </section>
    </main>
  );
}
