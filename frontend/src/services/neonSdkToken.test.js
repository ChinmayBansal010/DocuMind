import { afterEach, describe, expect, it, vi } from "vitest";
import { createAuthClient } from "@neon/auth";
import { BetterAuthReactAdapter } from "@neon/auth/react/adapters";

describe("Neon Auth JWT retrieval", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("bypasses the SDK session cache when requesting a JWT", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        session: { id: "session-1", token: "session-token" },
        user: { id: "user-1", email: "person@example.test" },
      }), {
        status: 200,
        headers: { "content-type": "application/json", "set-auth-jwt": "session-jwt" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: "access-jwt" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createAuthClient("https://auth.example.test", {
      adapter: BetterAuthReactAdapter(),
    });

    await client.signIn.email({ email: "person@example.test", password: "valid-password" });
    const result = await client.token({
      fetchOptions: { headers: { "X-Force-Fetch": "true" } },
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.data?.token).toBe("access-jwt");
    const tokenRequest = fetchMock.mock.calls[1][1];
    expect(tokenRequest.credentials).toBe("include");
    expect(new Headers(tokenRequest.headers).has("X-Force-Fetch")).toBe(false);
  });
});
