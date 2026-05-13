const LOCAL_API_FALLBACK = "http://localhost:8000";
const LOCAL_API_FALLBACK_ALT = "http://localhost:8001";

function isLocalHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

export function getApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    const { origin, hostname } = window.location;

    // Local frontend dev still talks to the local FastAPI backend on :8000.
    if (isLocalHostname(hostname)) {
      return LOCAL_API_FALLBACK;
    }

    // In deployed environments, default to same-origin so reverse-proxied
    // backends work without forcing localhost or causing mixed-content issues.
    return origin.replace(/\/$/, "");
  }

  return LOCAL_API_FALLBACK;
}

export function toUserFacingFetchError(error: unknown): Error {
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();
    if (msg.includes("failed to fetch") || msg.includes("networkerror")) {
      return new Error(
        "Cannot reach the backend API. Check that the backend is running and that NEXT_PUBLIC_API_URL is configured correctly."
      );
    }
    return error;
  }

  return new Error(
    "Cannot reach the backend API. Check that the backend is running and that NEXT_PUBLIC_API_URL is configured correctly."
  );
}

export async function fetchWithApiFallback(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const primaryBase = getApiBase();
  const primaryUrl = `${primaryBase}${path}`;

  try {
    return await fetch(primaryUrl, init);
  } catch (error) {
    const shouldTryAltLocalhost =
      typeof window !== "undefined" &&
      primaryBase === LOCAL_API_FALLBACK;

    if (!shouldTryAltLocalhost) {
      throw toUserFacingFetchError(error);
    }

    try {
      return await fetch(`${LOCAL_API_FALLBACK_ALT}${path}`, init);
    } catch (secondError) {
      throw toUserFacingFetchError(secondError);
    }
  }
}
