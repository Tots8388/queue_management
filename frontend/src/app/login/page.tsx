import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth";

import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "Staff sign in",
};

export default function LoginPage() {
  return (
    <AuthProvider>
      <div className="flex min-h-full flex-col justify-center bg-surface-muted">
        <main id="main" className="mx-auto w-full max-w-sm px-6 py-12">
          <h1 className="text-2xl font-semibold">Staff sign in</h1>
          <p className="mt-2 text-ink-muted">
            Kabarak University Medical Center — queue and patient flow.
          </p>
          <LoginForm />
          <p className="mt-8 text-sm text-ink-muted">
            Signing out at the end of your shift ends the session on the server,
            not just on this screen. Please sign out on shared terminals.
          </p>
        </main>
      </div>
    </AuthProvider>
  );
}
