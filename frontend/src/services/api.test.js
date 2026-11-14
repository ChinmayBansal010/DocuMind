import { afterEach, describe, expect, it, vi } from "vitest";

const getAccessToken = vi.hoisted(() => vi.fn());
vi.mock("./auth", () => ({ getAccessToken }));

import { api } from "./api";

describe("API authentication", () => {
  afterEach(() => {
    window.removeEventListener("documind:session-expired", sessionExpired);
    vi.clearAllMocks();
  });

  const sessionExpired = vi.fn();

  it("does not expire the session when token retrieval itself fails", async () => {
    getAccessToken.mockRejectedValue(new Error("No active Neon Auth session."));
    window.addEventListener("documind:session-expired", sessionExpired);

    await expect(api("/profile")).rejects.toThrow("No active Neon Auth session.");
    expect(sessionExpired).not.toHaveBeenCalled();
  });
});
