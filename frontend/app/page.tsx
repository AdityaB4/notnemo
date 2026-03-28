import Image from "next/image";
import Link from "next/link";

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

const starterTags = [
  "Hidden food spots",
  "Quiet anniversary plans",
  "Indie coffee places",
  "Artsy neighborhoods",
];

export default function Page() {
  return (
    <main className="intro-page">
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

      <section className="hero-shell">
        <div className="hero-copy">
          <span className="hero-badge">fische onboarding</span>
          <h1>Teach us your taste, and we&apos;ll hunt for internet deep cuts.</h1>
          <p className="hero-description">
            Start with a little context about what you love. We&apos;ll use it to
            personalize future recommendations and surface niche places that feel
            uncannily you.
          </p>

          <form className="intake-card">
            <label className="intake-label" htmlFor="about-you">
              What should we know about you?
            </label>
            <textarea
              id="about-you"
              className="response-input"
              placeholder="I love cozy places, seafood, slow evenings, handmade things, and anywhere that feels like a secret."
              rows={5}
            />

            <div className="tag-row" aria-label="Sample preferences">
              {starterTags.map((tag) => (
                <span className="tag-chip" key={tag}>
                  {tag}
                </span>
              ))}
            </div>

            <div className="card-footer">
              <p className="helper-text">
                This helps fische tune future searches to your vibe.
              </p>
              <Link className="continue-button" href="/explore">
                Start exploring
              </Link>
            </div>
          </form>
        </div>

        <aside className="hero-visual" aria-hidden="true">
          <div className="feature-card feature-card-top">
            <span className="feature-label">Signal</span>
            <strong>Preference profile</strong>
            <p>Built from mood, taste, and hidden-gem instincts.</p>
          </div>

          <div className="fish-stage">
            <div className="sonar-ring sonar-ring-one" />
            <div className="sonar-ring sonar-ring-two" />
            <div className="fish-image-wrap">
              <Image
                src="/fische-fish.png"
                alt="fische mascot fish"
                className="fish-image"
                width={440}
                height={440}
                priority
              />
            </div>
          </div>

          <div className="feature-card feature-card-bottom">
            <span className="feature-label">Output</span>
            <strong>Niche recommendations</strong>
            <p>Less algorithm sludge, more hidden corners worth the detour.</p>
          </div>
        </aside>
      </section>
    </main>
  );
}
