"use client";

import { auth } from "./firebase";

let cachedToken: string | null = null;
let cachedUid: string | null = null;
let cachedAt = 0;
let inflightTokenPromise: Promise<string | null> | null = null;

const TOKEN_CACHE_MS = 4 * 60 * 1000;

export async function getCachedAuthToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) {
    cachedToken = null;
    cachedUid = null;
    cachedAt = 0;
    inflightTokenPromise = null;
    return null;
  }

  const now = Date.now();
  if (
    cachedToken &&
    cachedUid === user.uid &&
    now - cachedAt < TOKEN_CACHE_MS
  ) {
    return cachedToken;
  }

  if (inflightTokenPromise) {
    return inflightTokenPromise;
  }

  inflightTokenPromise = user
    .getIdToken()
    .then((token) => {
      cachedToken = token;
      cachedUid = user.uid;
      cachedAt = Date.now();
      return token;
    })
    .catch((error) => {
      console.warn("Failed to get Firebase token", error);
      cachedToken = null;
      cachedUid = null;
      cachedAt = 0;
      return null;
    })
    .finally(() => {
      inflightTokenPromise = null;
    });

  return inflightTokenPromise;
}
