import type { Metadata } from "next";

import { Crest, HomeLink } from "@/components/ui";

import { TokenEntryForm } from "./TokenEntryForm";

export const metadata: Metadata = {
  title: "Check your queue",
};

export default function PatientEntryPage() {
  return (
    <div className="flex min-h-full flex-col bg-brand-gradient">
      <div className="mx-auto flex w-full max-w-md px-4 pt-4">
        <HomeLink />
      </div>

      <main
        id="main"
        className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12"
      >
        <div className="animate-fade-rise">
          <span className="grid size-14 place-items-center rounded-2xl bg-white/15 text-white ring-1 ring-white/25">
            <Crest className="size-9" />
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-white">
            Kabarak University Medical Center
          </h1>
          <p className="mt-2 text-lg text-brand-100">
            Enter the token on your slip to see where you are in the queue.
          </p>
        </div>

        <TokenEntryForm />

        <p className="mt-8 flex items-center gap-2 text-sm text-brand-100">
          <span aria-hidden="true">ℹ</span>
          If you have lost your token, please ask at the reception desk.
        </p>
      </main>

      <footer className="px-6 py-5 text-center text-sm text-brand-100/90">
        Prototype with fictional data only. Not for clinical use.
      </footer>
    </div>
  );
}
