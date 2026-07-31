import Link from "next/link";

import { BackendStatus } from "@/components/BackendStatus";
import { contracts } from "@/lib/contracts";

const CHANNELS = [
  {
    name: "Patient status",
    path: "/patient",
    description:
      "Your token, current stage, people ahead and a cautious waiting range.",
    theme: "border-role-reception",
  },
  {
    name: "Waiting-room display",
    path: "/display",
    description: "Anonymous tokens and destinations only. No names, no details.",
    theme: "border-brand-500",
  },
  {
    name: "Staff sign in",
    path: "/login",
    description:
      "Reception, vital signs, consultation and pharmacy dashboards.",
    theme: "border-role-nurse",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="bg-brand-700 text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-baseline gap-x-3 gap-y-1 px-6 py-5">
          <span className="text-lg font-semibold">
            Kabarak University Medical Center
          </span>
          <span className="text-brand-100">Queue &amp; patient flow</span>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
        <h1 className="text-2xl font-semibold">Where would you like to go?</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Every screen shares one queue state, so what you see here is what
          everyone else sees.
        </p>
        <div className="mt-4">
          <BackendStatus />
        </div>

        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {CHANNELS.map((channel) => (
            <li key={channel.path}>
              <Link
                href={channel.path}
                className={`block h-full rounded-lg border-l-4 bg-surface p-5 shadow-sm hover:bg-brand-50 ${channel.theme}`}
              >
                <h2 className="font-semibold">{channel.name}</h2>
                <p className="mt-1 text-sm text-ink-muted">
                  {channel.description}
                </p>
              </Link>
            </li>
          ))}
        </ul>

        <section className="mt-12">
          <h2 className="text-lg font-semibold">Stages</h2>
          <ol className="mt-3 flex flex-wrap gap-2">
            {contracts.stages.map((stage) => (
              <li
                key={stage.key}
                className="rounded-full bg-surface px-4 py-2 text-sm shadow-sm"
              >
                {stage.order}. {stage.label}
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line px-6 py-6 text-center text-sm text-ink-muted">
        Prototype with fictional data only. Not for clinical use.
      </footer>
    </div>
  );
}
