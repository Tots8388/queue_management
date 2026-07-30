/**
 * The shared queue vocabulary, imported from `shared/contracts.json` — the same
 * file the Django backend loads. Roles, stages and statuses are therefore
 * declared once for the whole system.
 *
 * `may_assign_priority` is used here only to decide which controls to render.
 * It is never the security boundary; the backend enforces spec FR3.
 */

import contractsJson from "@shared/contracts.json";

export const contracts = contractsJson;

export type RoleKey = (typeof contractsJson.roles)[number]["key"];
export type StageKey = (typeof contractsJson.stages)[number]["key"];
export type StageStatusKey = (typeof contractsJson.stage_statuses)[number]["key"];
export type PriorityKey = (typeof contractsJson.priorities)[number]["key"];
export type PresenceStatusKey =
  (typeof contractsJson.presence_statuses)[number]["key"];
export type PharmacyStateKey =
  (typeof contractsJson.pharmacy_states)[number]["key"];

type Entry = { key: string; label: string };

function lookup<T extends Entry>(entries: readonly T[], key: string): T | undefined {
  return entries.find((entry) => entry.key === key);
}

/** Display label for a key, falling back to the raw key rather than blank. */
export function labelFor(
  section: keyof typeof contractsJson,
  key: string,
): string {
  const entries = contractsJson[section];
  if (!Array.isArray(entries)) return key;
  return lookup(entries as readonly Entry[], key)?.label ?? key;
}

export const stageLabel = (key: string) => labelFor("stages", key);
export const priorityLabel = (key: string) => labelFor("priorities", key);
export const presenceLabel = (key: string) => labelFor("presence_statuses", key);
export const roleLabel = (key: string) => labelFor("roles", key);

/** The stage a visit moves to next, or null at the end of the journey. */
export function nextStage(current: string): StageKey | null {
  const index = contractsJson.stages.findIndex((s) => s.key === current);
  if (index < 0 || index >= contractsJson.stages.length - 1) return null;
  return contractsJson.stages[index + 1].key as StageKey;
}

/** Plain-language message shown to a patient for their priority level. */
export function patientMessageFor(priority: string): string {
  return (
    contractsJson.priorities.find((p) => p.key === priority)?.patient_message ??
    ""
  );
}
