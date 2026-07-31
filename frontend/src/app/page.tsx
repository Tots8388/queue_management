import Link from "next/link";

import { BackendStatus } from "@/components/BackendStatus";
import { Brand } from "@/components/ui";
import { contracts } from "@/lib/contracts";

const CHANNELS = [
  {
    name: "Patient status",
    path: "/patient",
    description:
      "Your token, current stage, people ahead and a cautious waiting range.",
    theme: "text-role-reception",
    ring: "hover:border-role-reception/40",
    icon: <PhoneIcon />,
  },
  {
    name: "Waiting-room display",
    path: "/display",
    description: "Anonymous tokens and destinations only. No names, no details.",
    theme: "text-brand-600",
    ring: "hover:border-brand-500/40",
    icon: <ScreenIcon />,
  },
  {
    name: "Staff sign in",
    path: "/login",
    description:
      "Reception, vital signs, consultation and pharmacy dashboards.",
    theme: "text-role-nurse",
    ring: "hover:border-role-nurse/40",
    icon: <BadgeIcon />,
  },
];

export default function Home() {
  return (
    <div className="flex min-h-full flex-col bg-app">
      <header className="bg-brand-gradient text-white shadow-brand">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-5">
          <Brand subtitle="Queue & patient flow" />
          <span className="hidden text-sm text-brand-100 sm:inline">
            Outpatient services
          </span>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
        <div className="animate-fade-rise">
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">
            Welcome
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            Where would you like to go?
          </h1>
          <p className="mt-2 max-w-2xl text-ink-muted">
            Every screen shares one queue state, so what you see here is what
            everyone else sees.
          </p>
          <div className="mt-4">
            <BackendStatus />
          </div>
        </div>

        <ul className="mt-8 grid gap-4 sm:grid-cols-3">
          {CHANNELS.map((channel) => (
            <li key={channel.path}>
              <Link
                href={channel.path}
                className={`card-interactive group flex h-full flex-col rounded-xl border border-line bg-surface p-5 shadow-sm ${channel.ring}`}
              >
                <span
                  aria-hidden="true"
                  className={`grid size-11 place-items-center rounded-lg bg-surface-muted ${channel.theme}`}
                >
                  {channel.icon}
                </span>
                <h2 className="mt-4 flex items-center gap-1.5 font-semibold">
                  {channel.name}
                  <span
                    aria-hidden="true"
                    className="text-ink-subtle transition-transform group-hover:translate-x-0.5"
                  >
                    →
                  </span>
                </h2>
                <p className="mt-1 text-sm text-ink-muted">
                  {channel.description}
                </p>
              </Link>
            </li>
          ))}
        </ul>

        <section className="mt-12">
          <h2 className="text-lg font-semibold">The patient journey</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Every visit moves through these stages in order.
          </p>
          <ol className="mt-4 flex flex-wrap items-center gap-y-3">
            {contracts.stages.map((stage, index) => (
              <li key={stage.key} className="flex items-center">
                <span className="inline-flex items-center gap-2.5 rounded-full border border-line bg-surface px-4 py-2 text-sm font-medium shadow-xs">
                  <span className="grid size-6 place-items-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700">
                    {stage.order}
                  </span>
                  {stage.label}
                </span>
                {index < contracts.stages.length - 1 && (
                  <span
                    aria-hidden="true"
                    className="mx-1.5 text-line-strong sm:mx-2.5"
                  >
                    →
                  </span>
                )}
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line bg-surface px-6 py-6 text-center text-sm text-ink-muted">
        Prototype with fictional data only. Not for clinical use.
      </footer>
    </div>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none">
      <rect
        x="7"
        y="2.5"
        width="10"
        height="19"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M10.5 18.5h3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ScreenIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none">
      <rect
        x="2.5"
        y="4"
        width="19"
        height="13"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M9 21h6M12 17v4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function BadgeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-6" fill="none">
      <rect
        x="3.5"
        y="4.5"
        width="17"
        height="15"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle cx="9" cy="10" r="2.2" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M6 16c.6-1.8 2-2.6 3-2.6s2.4.8 3 2.6M14.5 9.5h4M14.5 13h3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
