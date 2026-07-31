# High-fidelity screenshots

The figures in this folder are captured from the **running application** — not
mock-ups — against a production build with seeded fictional data.

| # | File | Screen | Viewport |
| --- | --- | --- | --- |
| 1 | `01-home.png` | Home hub | 1280 × 800 |
| 2 | `02-login.png` | Staff sign in | 1280 × 800 |
| 2b | `02b-login-invalid.png` | Sign in, invalid credentials | 1280 × 800 |
| 3 | `03-patient-entry.png` | Patient token entry | 390 × 844 |
| 4 | `04-patient-status.png` | Patient live status | 390 × 844 |
| 5 | `05-display-board.png` | Public display board | 1920 × 1080 |
| 6 | `06-reception.png` | Reception dashboard | 1440 × 900 |
| 7 | `07-vitals.png` | Vital signs dashboard | 1440 × 900 |
| 8 | `08-consultation.png` | Consultation dashboard | 1440 × 900 |
| 9 | `09-pharmacy.png` | Pharmacy dashboard | 1440 × 900 |
| 10 | `10-priority-dialog.png` | Priority dialog | 1440 × 900 |

## Regenerating them

```bat
:: 1. seed and start the backend
cd backend
.venv\Scripts\python manage.py seed_demo --reset
.venv\Scripts\python manage.py runserver 0.0.0.0:8000

:: 2. serve a PRODUCTION build of the frontend, in another terminal
cd frontend
npm run build
npm run start -- --port 3000

:: 3. capture
npm run screenshots
```

[`../../../frontend/scripts/capture-screenshots.mjs`](../../../frontend/scripts/capture-screenshots.mjs)
drives whichever Chrome or Edge is already installed via `puppeteer-core`,
rather than downloading a second browser.

### Two things the script does on purpose

- **Production build, not `npm run dev`.** The dev server overlays a Next.js
  dev-tools indicator, which lands in the middle of a full-page screenshot and
  looks like a defect in the interface.
- **It arranges representative data first** — registers a few patients so
  reception is not empty, calls a few so the board is not empty, and picks a
  **routine** patient for the patient-status figure. A patient with a clinical
  priority correctly sees "You will be seen as soon as possible" instead of a
  range, which is right behaviour but a poor illustration of the wait estimate.

An accurate screenshot of an unrepresentative state is still a misleading
figure, so the script sets the state up rather than photographing whatever
happened to be there.

## Notes

- The crest is a **placeholder** mark, not the official Kabarak crest. Swap in
  the real asset when it is available.
- Brand colour is the project's existing **Kabarak green**, documented and
  contrast-checked in [`../reference-prototypes.md`](../reference-prototypes.md).
- Every figure carries the "fictional data / not for clinical use" disclaimer,
  because a screenshot travels further than the caption that came with it.
