import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { getApiBase, toUserFacingFetchError } from "@/lib/api-base";

describe("api-base", () => {
  const originalWindow = globalThis.window;

  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    globalThis.window = originalWindow;
  });

  it("uses configured NEXT_PUBLIC_API_URL when present", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/");
    expect(getApiBase()).toBe("https://api.example.com");
  });

  it("uses localhost backend for local frontend origins", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    Object.defineProperty(globalThis, "window", {
      value: { location: { origin: "http://localhost:3000", hostname: "localhost" } },
      configurable: true,
    });
    expect(getApiBase()).toBe("http://localhost:8000");
  });

  it("uses same-origin in deployed browser contexts when env is missing", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    Object.defineProperty(globalThis, "window", {
      value: { location: { origin: "https://app.example.com", hostname: "app.example.com" } },
      configurable: true,
    });
    expect(getApiBase()).toBe("https://app.example.com");
  });

  it("normalizes browser fetch errors into a clearer API message", () => {
    const error = toUserFacingFetchError(new TypeError("Failed to fetch"));
    expect(error.message).toContain("Cannot reach the backend API");
  });
});
