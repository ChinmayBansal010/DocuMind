import { afterEach, describe, expect, it, vi } from "vitest";

const getAccessToken = vi.hoisted(() => vi.fn());
vi.mock("./auth", () => ({ getAccessToken }));

import { api } from "./api";

describe("API authentication", () => {
  afterEach(() => {
    window.removeEventListener("documind:session-expired", sessionExpired);
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  const sessionExpired = vi.fn();

  it("does not expire the session when token retrieval itself fails", async () => {
    getAccessToken.mockRejectedValue(new Error("No active Neon Auth session."));
    window.addEventListener("documind:session-expired", sessionExpired);

    await expect(api("/profile")).rejects.toThrow("No active Neon Auth session.");
    expect(sessionExpired).not.toHaveBeenCalled();
  });

  it("fetches a fresh token and retries once before expiring the session", async () => {
    getAccessToken.mockResolvedValueOnce("stale-jwt").mockResolvedValueOnce("fresh-jwt");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response('{"detail":"The access token is invalid or expired."}', {
        status: 401,
        headers: { "content-type": "application/json" },
      }))
      .mockResolvedValueOnce(new Response('{"id":"user-1"}', {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    window.addEventListener("documind:session-expired", sessionExpired);

    await expect(api("/profile")).resolves.toEqual({ id: "user-1" });
    expect(getAccessToken).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer stale-jwt");
    expect(fetchMock.mock.calls[1][1].headers.get("Authorization")).toBe("Bearer fresh-jwt");
    expect(sessionExpired).not.toHaveBeenCalled();
  });

  it("expires the session only after a refreshed token is also rejected", async () => {
    getAccessToken.mockResolvedValueOnce("first-jwt").mockResolvedValueOnce("second-jwt");
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"detail":"The access token is invalid or expired."}', {
      status: 401,
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    window.addEventListener("documind:session-expired", sessionExpired);

    await expect(api("/profile")).rejects.toThrow("The access token is invalid or expired.");
    expect(getAccessToken).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(sessionExpired).toHaveBeenCalledOnce();
  });
});
