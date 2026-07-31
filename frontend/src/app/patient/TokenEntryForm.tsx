"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function TokenEntryForm() {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = token.trim().toUpperCase();

    if (!trimmed) {
      // Plain language, and it says what to do rather than what went wrong.
      setError("Please type the token printed on your slip, for example T-041.");
      return;
    }

    setError(null);
    router.push(`/patient/${encodeURIComponent(trimmed)}`);
  }

  return (
    <form onSubmit={submit} className="mt-8" noValidate>
      <label htmlFor="token" className="block font-medium text-white">
        Your queue token
      </label>
      <input
        id="token"
        name="token"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        autoComplete="off"
        autoCapitalize="characters"
        // Not type="number": tokens contain letters and a separator.
        inputMode="text"
        aria-describedby={error ? "token-error" : "token-hint"}
        aria-invalid={error ? true : undefined}
        className="token-figure mt-2 w-full rounded-lg border-2 border-brand-100 bg-white px-4 py-3 text-2xl text-ink placeholder:text-ink-muted/60"
        placeholder="T-041"
      />
      <p id="token-hint" className="mt-2 text-sm text-brand-100">
        It is printed on the slip you were given at reception.
      </p>

      {error && (
        <p
          id="token-error"
          role="alert"
          className="mt-3 rounded-lg bg-white px-4 py-3 text-sm font-medium text-priority-emergency"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        className="mt-6 w-full rounded-lg bg-white px-4 py-3 text-lg font-semibold text-brand-700 hover:bg-brand-50"
      >
        Check my queue
      </button>
    </form>
  );
}
