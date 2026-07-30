# Frontend — patient, public display and staff dashboards

Next.js (App Router) + React + Tailwind. One codebase serves all six channels:
the patient status view, the anonymous waiting-room display, and the reception,
vitals, consultation and pharmacy dashboards.

Behaviour is specified in [`../spec.md`](../spec.md). The visual language comes
from the approved prototypes — see
[`../docs/design/reference-prototypes.md`](../docs/design/reference-prototypes.md).

```bash
npm install
npm run dev     # http://localhost:3000
npm run build
npm run lint
```

Or run the whole system with `start.bat` / `./start.sh` from the repo root.

## Conventions

- **Vocabulary comes from `shared/contracts.json`** via `@shared/*`. Never
  hard-code a stage, role or status string — import it from
  [`src/lib/contracts.ts`](./src/lib/contracts.ts).
- **Backend URL resolves at runtime.** `src/lib/config.ts` prefers
  `NEXT_PUBLIC_API_BASE_URL` but falls back to the host that served the page, so
  the clinic server's LAN address can change without a rebuild.
- **Design tokens live in `src/app/globals.css`.** Role colours, priority
  colours and the 44px minimum target size are defined there, not inline.
- **Priority is a staff-only concept.** Priority colours and tags may appear on
  staff dashboards only — never on the patient view or the public display
  (spec FR8).
- **Accessibility is a requirement, not a polish pass.** WCAG 2.2: visible
  focus, adequate contrast, generous target sizes, zoom never disabled, clear
  error text.

> **Next.js 16 note:** `params` and `searchParams` are async, Turbopack is the
> default bundler, and `next lint` is gone (`npm run lint` calls ESLint
> directly). See `node_modules/next/dist/docs/` before reaching for older APIs.
