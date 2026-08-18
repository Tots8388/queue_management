/**
 * Capture the high-fidelity figures described in
 * docs/design/screenshots/README.md.
 *
 * Uses puppeteer-core driving the browser already installed on this machine,
 * rather than pulling a second Chromium down — the clinic machine should not
 * need a 150MB download to produce a screenshot.
 *
 *   cd frontend
 *   DEMO_PASSWORD=… npm run screenshots
 *
 * Expects the stack running (start.bat) with the staff accounts seeded. No
 * patients are seeded anywhere in this project, so the script checks its own
 * cohort in and walks them along the journey before shooting. Output is written
 * relative to this file, so it lands in docs/design/screenshots wherever the
 * command is run from.
 */

import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

// Two applications, two origins. The patient app carries the landing page,
// token entry, patient status and the waiting-room board; the staff app
// carries the sign-in and the four dashboards. Sessions live in
// sessionStorage, which is per-origin, so the staff sign-in below has to be
// planted on the staff origin — planting it on the patient one would leave the
// dashboards signed out.
const PATIENT = process.env.PATIENT_URL ?? "http://localhost:3000";
const STAFF = process.env.STAFF_URL ?? "http://localhost:3001";
const API = process.env.API_URL ?? "http://localhost:8000/api";

// Resolved against this file, not the shell's working directory. Run from the
// repo root, `path.resolve("../docs/…")` lands outside the repository entirely
// and mkdirSync happily creates it — ten figures written somewhere nobody
// looks, with every step still reporting success.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "../../docs/design/screenshots");

// The seed accounts' password, which belongs in the environment rather than in
// a second committed copy that can drift from the seed command's own.
const PASSWORD = process.env.DEMO_PASSWORD;
if (!PASSWORD) {
  console.error(
    "DEMO_PASSWORD is not set. It is the password printed by\n" +
      "  python manage.py seed_demo\n" +
      "Set it in .env or in this shell before running the capture.",
  );
  process.exit(1);
}

const BROWSERS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];

const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 2 };
const WIDE = { width: 1280, height: 800, deviceScaleFactor: 2 };
const TV = { width: 1920, height: 1080, deviceScaleFactor: 1 };
const MOBILE = {
  width: 390,
  height: 844,
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
};

const executablePath = BROWSERS.find((candidate) => existsSync(candidate));
if (!executablePath) {
  console.error("No Chrome or Edge found. Install one, or set it in BROWSERS.");
  process.exit(1);
}

/**
 * One API call that refuses to fail quietly.
 *
 * A capture run that swallows a 401 does not produce no figures — it produces
 * ten plausible-looking figures of error and empty states, each announced with
 * a tick. Better to stop at the first sign that the stack is not in the state
 * the figures assume.
 */
async function call(pathname, { method = "GET", token, body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API}${pathname}`, { method, headers, body });
  if (!response.ok) {
    throw new Error(
      `${method} ${pathname} → ${response.status}: ${await response.text()}`,
    );
  }
  return response.json();
}

async function signInAs(username) {
  return call("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password: PASSWORD }),
  });
}

/** Sign in over the API and plant the tokens the app expects in sessionStorage. */
async function signIn(page, username) {
  const { access, refresh } = await signInAs(username);

  await page.goto(`${STAFF}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    (a, r) => {
      sessionStorage.setItem("queue.access", a);
      sessionStorage.setItem("queue.refresh", r);
    },
    access,
    refresh,
  );
}

/**
 * A token that is currently waiting, so the patient view has real content.
 *
 * Prefers a **routine** patient: one with a clinical priority sees "You will be
 * seen as soon as possible" instead of a range, which is correct behaviour but
 * makes a poor representative figure — the wait range is the thing the figure
 * is meant to show.
 */
async function liveToken() {
  const { access } = await signInAs("reception1");

  for (const stage of ["vitals", "consultation", "registration"]) {
    const queue = await call(`/queue/${stage}/`, { token: access });
    const routine = queue.visits?.find((v) => v.priority === "routine");
    if (routine) return routine.token;
  }

  const created = await call("/visits/check-in/", {
    method: "POST",
    token: access,
    body: "{}",
  });
  return created.token;
}

/**
 * Check a few patients in, so the reception queue is not empty.
 *
 * Nothing is seeded into the database, so every figure's content is created
 * here — through the same endpoints the staff dashboards call.
 */
async function registerPatients(howMany) {
  const { access } = await signInAs("reception1");

  const tokens = [];
  for (let index = 0; index < howMany; index += 1) {
    const created = await call("/visits/check-in/", {
      method: "POST",
      token: access,
      body: "{}",
    });
    tokens.push(created.token);
  }
  return tokens;
}

// Each stage is completed by the one role that holds the capability for it.
const STAFF_FOR_STAGE = {
  registration: "reception1",
  vitals: "nurse1",
  consultation: "clinician1",
  pharmacy: "pharmacy1",
};
const JOURNEY = ["registration", "vitals", "consultation", "pharmacy"];

/**
 * Walk patients along the journey so every dashboard has a queue to show.
 *
 * With no seeded history the whole cohort would otherwise sit in registration,
 * leaving vitals, consultation and pharmacy each photographed as "nobody is
 * waiting" — a true screenshot of an unrepresentative state.
 */
async function advance(tokens, throughStages) {
  const sessions = {};
  for (const [stage, username] of Object.entries(STAFF_FOR_STAGE)) {
    sessions[stage] = (await signInAs(username)).access;
  }

  for (const stage of JOURNEY.slice(0, throughStages)) {
    const access = sessions[stage];
    for (const token of tokens) {
      // Best-effort: a patient already moved on by an earlier pass, or one the
      // stage does not accept, must not abort a whole capture run.
      try {
        await call(`/visits/${token}/start/`, {
          method: "POST",
          token: access,
          body: "{}",
        });
        await call(`/visits/${token}/complete/`, {
          method: "POST",
          token: access,
          body: "{}",
        });
      } catch (error) {
        console.warn(`    (${token} not advanced past ${stage}: ${error.message})`);
      }
    }
  }
}

/**
 * Fill every stage: a cohort walked the furthest, then progressively shorter
 * ones, then a batch left at reception. Completing services also gives the
 * wait-range calculation the finished timings it needs (FR7) — without them
 * the patient figure shows "estimate unavailable".
 */
async function buildQueue() {
  for (const stages of [4, 3, 2, 1, 0]) {
    const tokens = await registerPatients(stages === 0 ? 4 : 3);
    if (stages) await advance(tokens, stages);
  }
}

/**
 * Call the first patient at each stage forward, one per stage.
 *
 * Through ``/start/`` rather than the presence endpoint, because that is the
 * button a real member of staff presses — and it records which desk or room
 * they were called to, which is the part of the board a patient acts on. Set
 * "called" directly and the figure shows highlighted tokens with no room
 * beside them: true of that database state, and untrue of the clinic.
 */
async function callPatients() {
  const called = [];
  for (const [stage, username] of Object.entries(STAFF_FOR_STAGE)) {
    const { access } = await signInAs(username);
    const queue = await call(`/queue/${stage}/`, { token: access });
    const first = (queue.visits ?? [])[0];
    if (!first) continue;

    // Best-effort per stage: one station having nobody to call must not abort
    // a whole capture run.
    try {
      await call(`/visits/${first.token}/start/`, {
        method: "POST",
        token: access,
        body: "{}",
      });
      called.push(`${first.token} (${stage})`);
    } catch (error) {
      console.warn(`    (${first.token} not called at ${stage}: ${error.message})`);
    }
  }
  console.log(`  called ${called.join(", ") || "(nobody — queue empty)"}`);
}

async function shoot(page, name, { viewport, url, before, fullPage = true }) {
  await page.setViewport(viewport);
  if (url) await page.goto(url, { waitUntil: "networkidle2" });
  if (before) await before(page);
  // Let the entrance animations settle so nothing is caught mid-fade.
  await new Promise((resolve) => setTimeout(resolve, 900));
  await page.screenshot({ path: path.join(OUT, name), fullPage });
  console.log(`  ✓ ${name}`);
}

await buildQueue();
const token = await liveToken();
console.log(`Using live token ${token}`);
mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath,
  headless: "new",
  args: ["--force-color-profile=srgb", "--hide-scrollbars"],
});
const page = await browser.newPage();

try {
  await shoot(page, "01-home.png", { viewport: WIDE, url: `${PATIENT}/` });
  await shoot(page, "02-login.png", { viewport: WIDE, url: `${STAFF}/login` });
  await shoot(page, "02b-login-invalid.png", {
    viewport: WIDE,
    url: `${STAFF}/login`,
    before: async (p) => {
      await p.type("#username", "nurse1");
      await p.type("#password", "wrong-password");
      await p.click('button[type="submit"]');
      await new Promise((r) => setTimeout(r, 1200));
    },
  });
  await shoot(page, "03-patient-entry.png", {
    viewport: MOBILE,
    url: `${PATIENT}/patient`,
  });
  await shoot(page, "04-patient-status.png", {
    viewport: MOBILE,
    url: `${PATIENT}/patient/${token}`,
  });
  // The board lists everyone in the clinic, so the cohort above already fills
  // it. Calling one patient forward at each station adds the state the board
  // exists to shout — a highlighted token, with the room to walk to.
  await callPatients();
  await shoot(page, "05-display-board.png", {
    viewport: TV,
    url: `${PATIENT}/display`,
    fullPage: false,
  });

  for (const [username, route, file] of [
    ["reception1", "reception", "06-reception.png"],
    ["nurse1", "vitals", "07-vitals.png"],
    ["clinician1", "consultation", "08-consultation.png"],
    ["pharmacy1", "pharmacy", "09-pharmacy.png"],
  ]) {
    await signIn(page, username);
    await shoot(page, file, {
      viewport: DESKTOP,
      url: `${STAFF}/staff/${route}`,
    });
  }

  // Priority dialog, opened from the station allowed to use it.
  await signIn(page, "nurse1");
  await shoot(page, "10-priority-dialog.png", {
    viewport: DESKTOP,
    url: `${STAFF}/staff/vitals`,
    fullPage: false,
    before: async (p) => {
      const opened = await p.evaluate(() => {
        const button = [...document.querySelectorAll("button")].find(
          (b) => b.textContent?.trim() === "Priority",
        );
        button?.click();
        return Boolean(button);
      });
      if (!opened) console.warn("    (no Priority button — queue may be empty)");
      await new Promise((r) => setTimeout(r, 800));
    },
  });
} finally {
  await browser.close();
}

console.log(`\nSaved to ${OUT}`);
