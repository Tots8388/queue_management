"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function LoginForm() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const user = await signIn(username, password);

      if (!user.dashboard) {
        // Supervisor and IT/Support hold no capabilities until governance item
        // G4 is settled. Say so plainly rather than dropping them on an empty
        // screen and letting them think the system is broken.
        setError(
          `Signed in as ${user.role_label}, but this role has no dashboard yet. ` +
            "Management and IT/Support access is awaiting governance sign-off.",
        );
        return;
      }

      router.push(user.dashboard);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not sign in.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
      <div>
        <label htmlFor="username" className="block font-medium">
          Username
        </label>
        <input
          id="username"
          name="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          required
          className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5"
        />
      </div>

      <div>
        <label htmlFor="password" className="block font-medium">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
          className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5"
        />
      </div>

      <ErrorNote message={error} />

      <Button type="submit" fullWidth disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
