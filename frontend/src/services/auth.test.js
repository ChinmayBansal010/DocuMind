import { afterEach, describe, expect, it, vi } from "vitest";

const neon = vi.hoisted(() => ({
  client: {
    token: vi.fn(),
    getSession: vi.fn(),
  },
}));

vi.mock("@neon/auth", () => ({ createAuthClient: () => neon.client }));
vi.mock("@neon/auth/react/adapters", () => ({ BetterAuthReactAdapter: () => ({}) }));
vi.stubEnv("VITE_NEON_AUTH_URL", "https://auth.example.test");

const { getAccessToken } = await import("./auth");

describe("Neon access token", () => {
  afterEach(() => vi.clearAllMocks());

  it("uses the JWT returned by Neon Auth's token endpoint", async () => {
    neon.client.token.mockResolvedValue({ data: { token: "access-jwt" }, error: null });

    await expect(getAccessToken()).resolves.toBe("access-jwt");
  });

  it("does not fall back to a potentially expired session JWT when token retrieval fails", async () => {
    neon.client.token.mockResolvedValue({ data: null, error: { message: "Auth service unavailable" } });

    await expect(getAccessToken()).rejects.toThrow("Auth service unavailable");
    expect(neon.client.getSession).not.toHaveBeenCalled();
  });
});
