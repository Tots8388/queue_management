/**
 * Capture the high-fidelity figures described in
 * docs/design/screenshots/README.md.
 *
 * Uses puppeteer-core driving the browser already installed on this machine,
 * rather than pulling a second Chromium down — the clinic machine should not
 * need a 150MB download to produce a screenshot.
 *
 *   node scripts/capture-screenshots.mjs
 *
 * Expects the stack running (start.bat) with seeded data.
 */

import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

import puppeteer from "puppeteer-core";

const FRONTEND = process.env.FRONTEND_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000/api";
const OUT = path.resolve("../docs/design/screenshots");
const PASSWORD = "prototype-demo-only";

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

/** Sign in over the API and plant the tokens the app expects in sessionStorage. */
async function signIn(page, username) {
  const response = await fetch(`${API}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password: PASSWORD }),
  });
  if (!response.ok) throw new Error(`sign-in failed for ${username}`);
  const { access, refresh } = await response.json();

  await page.goto(`${FRONTEND}/login`, { waitUntil: "domcontentloaded" });
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
  const login = await fetch(`${API}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "reception1", password: PASSWORD }),
  }).then((r) => r.json());

  for (const stage of ["vitals", "consultation", "registration"]) {
    const queue = await fetch(`${API}/queue/${stage}/`, {
      headers: { Authorization: `Bearer ${login.access}` },
    }).then((r) => r.json());
    const routine = queue.visits?.find((v) => v.priority === "routine");
    if (routine) return routine.token;
  }

  const created = await fetch(`${API}/visits/check-in/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${login.access}`,
    },
    body: "{}",
  }).then((r) => r.json());
  return created.token;
}

/**
 * Check a few patients in, so the reception queue is not empty.
 *
 * The seed starts everyone past registration, which leaves reception showing
 * "nobody is waiting" — a true screenshot of an unrepresentative state.
 */
async function registerPatients(howMany) {
  const login = await fetch(`${API}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "reception1", password: PASSWORD }),
  }).then((r) => r.json());

  for (let index = 0; index < howMany; index += 1) {
    await fetch(`${API}/visits/check-in/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${login.access}`,
      },
      body: "{}",
    });
  }
}

/** Put a few patients into "called" so the board has something to show. */
async function callPatients(howMany) {
  const login = await fetch(`${API}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "nurse1", password: PASSWORD }),
  }).then((r) => r.json());
  const auth = { Authorization: `Bearer ${login.access}` };

  const called = [];
  for (const stage of ["vitals", "consultation", "pharmacy"]) {
    if (called.length >= howMany) break;
    const queue = await fetch(`${API}/queue/${stage}/`, { headers: auth }).then(
      (r) => r.json(),
    );
    for (const visit of queue.visits ?? []) {
      if (called.length >= howMany) break;
      const response = await fetch(`${API}/visits/${visit.token}/presence/`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({ presence: "called" }),
      });
      if (response.ok) called.push(visit.token);
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

await registerPatients(4);
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
  await shoot(page, "01-home.png", { viewport: WIDE, url: `${FRONTEND}/` });
  await shoot(page, "02-login.png", { viewport: WIDE, url: `${FRONTEND}/login` });
  await shoot(page, "02b-login-invalid.png", {
    viewport: WIDE,
    url: `${FRONTEND}/login`,
    before: async (p) => {
      await p.type("#username", "nurse1");
      await p.type("#password", "wrong-password");
      await p.click('button[type="submit"]');
      await new Promise((r) => setTimeout(r, 1200));
    },
  });
  await shoot(page, "03-patient-entry.png", {
    viewport: MOBILE,
    url: `${FRONTEND}/patient`,
  });
  await shoot(page, "04-patient-status.png", {
    viewport: MOBILE,
    url: `${FRONTEND}/patient/${token}`,
  });
  // The board only lists patients who are actually being called, so call a few
  // first — an empty board is a true screenshot of an untrue situation.
  await callPatients(3);
  await shoot(page, "05-display-board.png", {
    viewport: TV,
    url: `${FRONTEND}/display`,
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
      url: `${FRONTEND}/staff/${route}`,
    });
  }

  // Priority dialog, opened from the station allowed to use it.
  await signIn(page, "nurse1");
  await shoot(page, "10-priority-dialog.png", {
    viewport: DESKTOP,
    url: `${FRONTEND}/staff/vitals`,
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
