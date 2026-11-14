import { getAccessToken } from "./auth";

const API = "/api/v1";

async function authenticatedFetch(path, options = {}) {
  const send = async (token) => {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return fetch(`${API}${path}`, { ...options, headers, credentials: "include" });
  };

  let response = await send(await getAccessToken());
  if (response.status === 401) {
    response = await send(await getAccessToken());
  }
  return response;
}

function notifySessionExpired(detail) {
  window.dispatchEvent(new CustomEvent("documind:session-expired", {
    detail: detail || "The API rejected the current authentication token.",
  }));
}

export async function api(path, options = {}) {
  const response = await authenticatedFetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message = typeof data === "object" ? data.detail || data.message : data;
    if (response.status === 401) notifySessionExpired(message);
    throw new Error(message || `Request failed (${response.status}).`);
  }
  return data;
}

export async function download(path) {
  const response = await authenticatedFetch(path);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) notifySessionExpired(data.detail);
    throw new Error(data.detail || "Report export failed.");
  }
  const disposition = response.headers.get("content-disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || "contract-report";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
