import type { Metadata } from "next";

import { TokenEntryForm } from "./TokenEntryForm";

export const metadata: Metadata = {
  title: "Check your queue",
};

export default function PatientEntryPage() {
  return (
    <div className="flex min-h-full flex-col bg-brand-700">
      <main
        id="main"
        className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12"
      >
        <h1 className="text-2xl font-semibold text-white">
          Kabarak University Medical Center
        </h1>
        <p className="mt-2 text-brand-100">
          Enter the token on your slip to see where you are in the queue.
        </p>

        <TokenEntryForm />

        <p className="mt-8 text-sm text-brand-100">
          If you have lost your token, please ask at the reception desk.
        </p>
      </main>
    </div>
  );
}
