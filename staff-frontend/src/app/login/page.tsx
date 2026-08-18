import type { Metadata } from "next";

import { Brand } from "@shared/ui/components/ui";
import { AuthProvider } from "@/lib/auth";

import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "Staff sign in",
};

export default function LoginPage() {
  return (
    <AuthProvider>
      <div className="flex min-h-dvh flex-col bg-app">
        <header className="bg-brand-gradient text-white shadow-brand">
          <div className="mx-auto flex max-w-5xl items-center px-6 py-4">
            <Brand subtitle="Staff access" />
          </div>
        </header>

        <main
          id="main"
          className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-6 py-12"
        >
          <div className="animate-fade-rise rounded-2xl border border-line bg-surface p-7 shadow-lg">
            <h1 className="text-2xl font-semibold tracking-tight">
              Staff sign in
            </h1>
            <p className="mt-1.5 text-sm text-ink-muted">
              Reception, vital signs, consultation and pharmacy dashboards.
            </p>
            <LoginForm />
          </div>

          <p className="mt-6 rounded-xl border border-line bg-surface-muted/70 px-4 py-3 text-sm text-ink-muted">
            Signing out at the end of your shift ends the session on the server,
            not just on this screen. Please sign out on shared terminals.
          </p>
        </main>

        <footer className="border-t border-line bg-surface px-6 py-5 text-center text-sm text-ink-muted">
          Prototype with fictional data only. Not for clinical use.
        </footer>
      </div>
    </AuthProvider>
  );
}
