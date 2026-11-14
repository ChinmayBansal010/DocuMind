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

  it("uses the JWT attached to the active session when the token endpoint has no token", async () => {
    neon.client.token.mockResolvedValue({ data: {}, error: null });
    neon.client.getSession.mockResolvedValue({
      data: { session: { token: "session-jwt" }, user: { id: "user-1" } },
      error: null,
    });

    await expect(getAccessToken()).resolves.toBe("session-jwt");
  });

  it("surfaces the Neon Auth error when neither endpoint provides a token", async () => {
    neon.client.token.mockResolvedValue({ data: null, error: { message: "Auth service unavailable" } });
    neon.client.getSession.mockResolvedValue({ data: { session: null, user: null }, error: null });

    await expect(getAccessToken()).rejects.toThrow("Auth service unavailable");
  });
});
