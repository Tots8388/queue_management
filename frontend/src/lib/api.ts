/**
 * Talking to the queue server.
 *
 * Tokens live in `sessionStorage`, not `localStorage`, and that is deliberate:
 * clinic terminals are shared between shifts, and a session that survives the
 * browser closing is a session the next person inherits.
 */

import { apiUrl } from "./config";

const ACCESS_KEY = "queue.access";
const REFRESH_KEY = "queue.refresh";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the server is unreachable — the manual fallback signal. */
  get isOffline(): boolean {
    return this.status === 0;
  }
}

export const tokens = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    sessionStorage.setItem(ACCESS_KEY, access);
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  },
};

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    // DRF field errors: surface the first one rather than a bare status code,
    // so staff see "A reason is required", not "400".
    const first = Object.values(body ?? {}).flat()[0];
    if (typeof first === "string") return first;
  } catch {
    // Fall through to the generic message.
  }
  return `Request failed (${response.status})`;
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;

  const response = await fetch(apiUrl("auth/refresh/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!response.ok) {
    tokens.clear();
    return false;
  }

  const body = await response.json();
  tokens.set(body.access, body.refresh);
  return true;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  /** Public endpoints (patient status, display board) send no credentials. */
  authenticated?: boolean;
};

export async function api<T = unknown>(
  path: string,
  { method = "GET", body, authenticated = true }: RequestOptions = {},
): Promise<T> {
  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";

    const access = authenticated ? tokens.access : null;
    if (access) headers.Authorization = `Bearer ${access}`;

    return fetch(apiUrl(path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  };

  let response: Response;
  try {
    response = await send();
  } catch {
    // Network-level failure. Staff need to know to switch to paper, so this
    // must be distinguishable from a rejected request.
    throw new ApiError(0, "Cannot reach the queue server.");
  }

  // One retry after a silent token refresh, so a shift does not get bounced to
  // the sign-in screen mid-task when an access token quietly expires.
  if (response.status === 401 && authenticated && (await refreshAccessToken())) {
    response = await send();
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
