/**
 * Shapes the queue server returns. Vocabulary keys come from
 * `shared/contracts.json` via `contracts.ts`, so these describe structure only.
 */

import type {
  PharmacyStateKey,
  PresenceStatusKey,
  PriorityKey,
  RoleKey,
  StageKey,
  StageStatusKey,
} from "./contracts";

export type ServiceCounter = {
  id: number;
  name: string;
  stage: StageKey;
  is_active: boolean;
};

export type StaffUser = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: RoleKey;
  role_label: string;
  capabilities: string[];
  /** Null for roles whose boundary awaits governance sign-off (G4). */
  dashboard: string | null;
  default_counter: ServiceCounter | null;
};

/** A visit as staff see it. Carries priority — never render on public screens. */
export type StaffVisit = {
  id: number;
  token: string;
  current_stage: StageKey;
  stage_label: string;
  stage_status: StageStatusKey;
  priority: PriorityKey;
  priority_label: string;
  presence_status: PresenceStatusKey;
  presence_label: string;
  counter: string | null;
  awaiting_tests: boolean;
  check_in_time: string;
  waiting_minutes: number;
  last_updated: string;
};

export type StageSummary = {
  stage: StageKey;
  waiting: number;
  in_progress: number;
  stepped_away: number;
  emergency: number;
  urgent: number;
};

export type StaffQueueState = {
  channel?: "staff";
  stage: StageKey;
  summary: StageSummary;
  visits: StaffVisit[];
  generated_at?: string;
};

/**
 * The wait figure. Always a range or an explicit "unavailable" — never a
 * countdown, and never a single number (spec).
 */
export type WaitRange = {
  available: boolean;
  text: string;
  low_minutes?: number;
  high_minutes?: number;
};

/** A patient's own view. Deliberately has no priority field. */
export type PatientStatus = {
  channel?: "patient";
  token: string;
  current_stage: StageKey;
  stage_label: string;
  next_stage_label: string | null;
  stage_status: StageStatusKey;
  presence_status: PresenceStatusKey;
  people_ahead: number | null;
  wait_range: WaitRange;
  last_updated: string;
};

/** One line on the public board. Two fields, by design (spec FR8). */
export type DisplayRow = {
  token: string;
  destination: string;
};

export type DisplayState = {
  channel?: "display";
  rows: DisplayRow[];
  generated_at?: string;
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: StaffUser;
};

export type PharmacyState = PharmacyStateKey;
