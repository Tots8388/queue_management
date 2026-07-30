/**
 * Runtime configuration for reaching the backend.
 *
 * The system is deployed on the Medical Center's LAN, where the server's
 * address can change (new machine, new DHCP lease) without anyone rebuilding
 * the frontend. So rather than relying only on a build-time-inlined
 * NEXT_PUBLIC_ value, we fall back to the host that served the page — a phone
 * or display screen that can load the app can always reach the API the same
 * way.
 */

const DEFAULT_BACKEND_PORT = "8000";

function fromBrowserOrigin(protocol: "http" | "ws"): string {
  const { hostname, protocol: pageProtocol } = window.location;
  const secure = pageProtocol === "https:";
  const scheme =
    protocol === "http" ? (secure ? "https" : "http") : secure ? "wss" : "ws";
  return `${scheme}://${hostname}:${DEFAULT_BACKEND_PORT}`;
}

/** Base URL for REST calls, e.g. `http://192.168.1.50:8000`. */
export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") {
    return `http://localhost:${DEFAULT_BACKEND_PORT}`;
  }
  return fromBrowserOrigin("http");
}

/** Base URL for WebSocket connections, e.g. `ws://192.168.1.50:8000`. */
export function wsBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") {
    return `ws://localhost:${DEFAULT_BACKEND_PORT}`;
  }
  return fromBrowserOrigin("ws");
}

export const apiUrl = (path: string) =>
  `${apiBaseUrl()}/api/${path.replace(/^\//, "")}`;
