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

import { api, tokens } from "./api";
import type { LoginResponse, StaffUser } from "./types";

type AuthState = {
  user: StaffUser | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<StaffUser>;
  signOut: () => Promise<void>;
  can: (capability: string) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<StaffUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Restore the session on load, so a page refresh mid-shift does not force a
  // fresh sign-in.
  useEffect(() => {
    let cancelled = false;

    async function restore() {
      if (!tokens.access) {
        setLoading(false);
        return;
      }
      try {
        const me = await api<StaffUser>("auth/me/");
        if (!cancelled) setUser(me);
      } catch {
        tokens.clear();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const result = await api<LoginResponse>("auth/login/", {
      method: "POST",
      body: { username, password },
      authenticated: false,
    });
    tokens.set(result.access, result.refresh);
    setUser(result.user);
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
    router.push("/login");
  }, [router]);

  const can = useCallback(
    (capability: string) => Boolean(user?.capabilities.includes(capability)),
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, signIn, signOut, can }),
    [user, loading, signIn, signOut, can],
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
