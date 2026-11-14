import { createAuthClient } from "@neon/auth";
import { BetterAuthReactAdapter } from "@neon/auth/react/adapters";

const authUrl = import.meta.env.VITE_NEON_AUTH_URL;

export const authClient = authUrl
  ? createAuthClient(authUrl, { adapter: BetterAuthReactAdapter() })
  : null;

export async function getAccessToken() {
  if (!authClient) throw new Error("Neon Auth is not configured for this frontend.");
  // The SDK's session cache also intercepts /token, so force a real JWT request.
  const tokenResult = await authClient.token({
    fetchOptions: { headers: { "X-Force-Fetch": "true" } },
  });
  if (tokenResult.data?.token) return tokenResult.data.token;

  if (tokenResult.error) throw new Error(tokenResult.error.message || "Unable to retrieve an access token.");
  throw new Error("Neon Auth returned no access token for this session. Please sign in again.");
}
