// app/lib/newsAPI.ts

// Existing behavior for verification logic (KEEP)
import { runVerification } from "./geminiService";

export async function searchNewsThroughBackend(query: string) {
  return await runVerification({
    type: "text",
    content: query,
  });
}

// NEW function for direct news search (does NOT interfere)
export async function searchNews(query: string) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_URL}/search-news?query=${encodeURIComponent(query)}`
  );

  if (!res.ok) throw new Error("Failed to fetch news");
  return await res.json();
}
