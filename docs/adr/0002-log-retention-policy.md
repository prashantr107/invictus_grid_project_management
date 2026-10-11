# ADR-0002: Retention and archiving policy for `audit_logs` and `activity_logs`

- **Status:** Accepted
- **Date:** 2026-10-11
- **Relates to:** `PROJECT_CHECKLIST.md` Phase 3 "Data & lifecycle", SRS §3.12 (activity/audit logging) / §4.2 (integrity)
- **Source-of-truth guard:** PRD §24 / TRD §22 — logging and retention behavior is changed only with an explicit product decision; this ADR records that decision.

## Context

Both `audit_logs` and `activity_logs` (migration `0001` / `0003`) are append-only tables with a `created_at` timestamp and no retention policy. At the MVP's target size (~120–150 members, one organization) they grow linearly and without bound. SRS §3.12 requires:

- **Activity logs** — user-facing project/task history.
- **Audit logs** — privileged/security-sensitive actions (user creation, deactivation, role changes, project creation, membership changes).
- Logs must never contain passwords, tokens, or other secrets (§3.12).

The two tables have different audiences and different value over time, so they should not share one policy.

## Decision

**Audit logs are retained indefinitely** (never automatically purged). They are the security record of privileged actions and are the cheapest to keep. Retention is governed by the organization's record-keeping obligation, which the MVP cannot know; the default is therefore "keep everything".

**Activity logs are retained for 180 days** and then may be purged. Activity history is user-facing convenience data (recent project/task events), and older entries add little product value while dominating table size.

**MVP implementation: keep both tables append-only, but make them prunable.** No background job ships in the MVP. Instead:

1. A documented, manual purge procedure exists for operators:
   ```sql
   -- Activity history older than the retention window (safe, human-facing data).
   DELETE FROM activity_logs WHERE created_at < now() - interval '180 days';

   -- Audit logs are NOT purged by default. If a legal retention window is
   -- agreed, prune explicitly, e.g.:
   -- DELETE FROM audit_logs WHERE created_at < now() - interval '2 years';
   ```
2. The purge is an **operational release step**, not an Alembic migration: retention depends on deployment date, not schema version, and deleting rows inside a migration makes downgrades lossy.
3. `created_at` is the retention key. Both tables already store it as `DateTime(timezone=True)`; the SRS §4.2 timezone rule (UTC) applies.

When pagination/filtering of logs is added (Phase 9), add supporting indexes on `(created_at)` (and/or `(project_id, created_at)`) so the purge and the list queries stay off sequential scans. This ADR does not add those indexes yet to avoid shipping an index whose access pattern is not final.

## Consequences

- **Security record preserved** — audit history is never silently destroyed; any audit purge is a deliberate, logged operational action.
- **Bounded growth for the large table** — activity history stays small, so lists and simple dashboards remain fast at MVP scale.
- **No automatic deletion in the MVP** — nothing is lost without an explicit operator action; a misconfigured job cannot destroy data.
- **Reversible decision** — moving audit logs to a bounded window, or adding an automated archival job, is a follow-up operational change that does not require a schema migration.
- **Follow-up (not blocking):** if/when activity-log volume justifies it, archive purged rows to cold storage before deleting, and add the `created_at` indexes noted above.

## Alternatives considered

**One shared retention window for both tables.** Rejected: it either shortens security-record retention (bad for audits) or forces user-facing history to grow unbounded (bad for performance).

**Automated nightly purge job in the MVP.** Rejected for now: it adds a scheduler/worker dependency the MVP does not otherwise need, and an unattended job that deletes security-adjacent data is riskier than a documented manual step at this size.

**Partitioning / archive tables now.** Deferred: premature at ~150 members; revisit if `activity_logs` exceeds a manageable row count.
