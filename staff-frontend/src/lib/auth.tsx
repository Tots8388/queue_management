"use client";

/**
 * Staff session state.
 *
 * Capabilities from the server decide which controls render. That is a
 * usability measure, not a security one — every action is checked again on the
 * server, and hiding a button has never stopped anybody.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api, ApiError, tokens } from "@shared/ui/lib/api";
import type { LoginResponse, StaffUser } from "@shared/ui/lib/types";

type AuthState = {
  user: StaffUser | null;
  loading: boolean;
  /**
   * The session is intact but the server cannot be reached. Distinct from
   * signed-out, and the distinction matters: one is fixed by signing in, the
   * other by the network coming back.
   */
  offline: boolean;
  retry: () => void;
  signIn: (username: string, password: string) => Promise<StaffUser>;
  signOut: () => Promise<void>;
  can: (capability: string) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

type Session =
  | { kind: "staff"; user: StaffUser }
  | { kind: "offline" }
  | { kind: "signed-out" };

/**
 * Work out where the session stands, without touching React state.
 *
 * The three outcomes are kept apart deliberately. Treating an unreachable
 * server as a signed-out session would clear the tokens and sign the whole
 * clinic out the moment the network dipped — demanding a fresh sign-in during
 * exactly the outage the paper fallback exists to cover.
 */
async function loadSession(): Promise<Session> {
  if (!tokens.access) return { kind: "signed-out" };

  try {
    return { kind: "staff", user: await api<StaffUser>("auth/me/") };
  } catch (caught) {
    if (caught instanceof ApiError && caught.isOffline) return { kind: "offline" };
    // A rejected session, on the other hand, is over.
    tokens.clear();
    return { kind: "signed-out" };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<StaffUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const router = useRouter();

  const apply = useCallback((session: Session) => {
    setUser(session.kind === "staff" ? session.user : null);
    setOffline(session.kind === "offline");
    setLoading(false);
  }, []);

  // Restore the session on load, so a page refresh mid-shift does not force a
  // fresh sign-in.
  useEffect(() => {
    let cancelled = false;

    loadSession().then((session) => {
      if (!cancelled) apply(session);
    });

    return () => {
      cancelled = true;
    };
  }, [apply]);

  const retry = useCallback(async () => {
    setLoading(true);
    apply(await loadSession());
  }, [apply]);

  const signIn = useCallback(async (username: string, password: string) => {
    const result = await api<LoginResponse>("auth/login/", {
      method: "POST",
      body: { username, password },
      authenticated: false,
    });
    tokens.set(result.access, result.refresh);
    setUser(result.user);
    setOffline(false);
    return result.user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      // Revoke server-side. On a shared terminal, clearing the browser's copy
      // is not enough.
      await api("auth/logout/", {
        method: "POST",
        body: { refresh: tokens.refresh },
      });
    } catch {
      // Even if the call fails, the local session must end.
    }
    tokens.clear();
    setUser(null);
    setOffline(false);
    router.push("/login");
  }, [router]);

  const can = useCallback(
    (capability: string) => Boolean(user?.capabilities.includes(capability)),
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, offline, retry, signIn, signOut, can }),
    [user, loading, offline, retry, signIn, signOut, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
