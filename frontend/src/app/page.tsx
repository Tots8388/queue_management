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
    name: "Reception",
    path: "/staff/reception",
    description: "Register a patient, record check-in, issue a token.",
    theme: "border-role-reception",
  },
  {
    name: "Vital signs",
    path: "/staff/vitals",
    description: "Take vitals, set clinical priority, send to the clinician.",
    theme: "border-role-nurse",
  },
  {
    name: "Consultation",
    path: "/staff/consultation",
    description: "Consult, set priority with a reason, send to pharmacy.",
    theme: "border-role-clinician",
  },
  {
    name: "Pharmacy",
    path: "/staff/pharmacy",
    description: "Mark medicine ready, issued or unavailable, and close.",
    theme: "border-role-pharmacy",
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
        <h1 className="text-2xl font-semibold">Prototype — screens</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Six channels share one queue state. Each is built in Phase 5; this page
          is the entry point while the backend is being built.
        </p>
        <div className="mt-4">
          <BackendStatus />
        </div>

        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {CHANNELS.map((channel) => (
            <li
              key={channel.path}
              className={`rounded-lg border-l-4 bg-surface p-5 shadow-sm ${channel.theme}`}
            >
              <h2 className="font-semibold">{channel.name}</h2>
              <p className="mt-1 text-sm text-ink-muted">{channel.description}</p>
              <p className="mt-3 font-mono text-xs text-ink-muted">
                {channel.path}
              </p>
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
