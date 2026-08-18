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
      setError("Please type the token printed on your slip, for example K492.");
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
        // Not type="number": a token starts with a letter.
        inputMode="text"
        aria-describedby={error ? "token-error" : "token-hint"}
        aria-invalid={error ? true : undefined}
        // This field sits on the dark brand gradient, so it overrides the global
        // ink focus ring with a white one rather than removing it: near-black on
        // dark green is the one background where the default would disappear.
        className="token-figure mt-2 w-full rounded-xl border-2 border-white/70 bg-white px-4 py-4 text-center text-3xl font-semibold text-ink shadow-lg transition-shadow placeholder:font-normal placeholder:text-ink-subtle/60 focus:border-white focus:shadow-[0_0_0_4px_rgba(255,255,255,0.35)] focus-visible:outline-white"
        placeholder="K492"
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
        className="mt-6 flex min-h-target w-full items-center justify-center gap-2 rounded-xl bg-white px-4 py-4 text-lg font-semibold text-brand-700 shadow-lg transition-[background-color,transform] hover:bg-brand-50 active:translate-y-px"
      >
        Check my queue
        <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}
