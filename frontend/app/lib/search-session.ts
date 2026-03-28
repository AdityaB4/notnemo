"use client";

export type SearchSession = {
  about: string;
  explore: string;
};

const STORAGE_KEY = "fische-search-session";

export function readSearchSession(): SearchSession {
  if (typeof window === "undefined") {
    return { about: "", explore: "" };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { about: "", explore: "" };
    }

    const parsed = JSON.parse(raw) as Partial<SearchSession>;
    return {
      about: typeof parsed.about === "string" ? parsed.about : "",
      explore: typeof parsed.explore === "string" ? parsed.explore : "",
    };
  } catch {
    return { about: "", explore: "" };
  }
}

export function writeSearchSession(next: Partial<SearchSession>): SearchSession {
  const current = readSearchSession();
  const merged = {
    about: next.about ?? current.about,
    explore: next.explore ?? current.explore,
  };

  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  }

  return merged;
}
