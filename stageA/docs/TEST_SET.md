# Test-split templates: plan and freezing rules

**Status (2026-10-01): written and frozen.** Harness v0.3 (same day) changed when compaction happens,
not the templates; the fingerprint is unchanged. Under the v0.3 rule the shortest correct path compacts in
56 of 60 templates; T-P15, T-C12, T-C15 and T-C18 can be solved with a single write (see `DEVIATIONS.md`). 60 templates in `sid/tasks/test_*.py`, spec and full review
history in `docs/TEST_SET_DRAFT_zh.md`, fingerprint in `docs/FROZEN_TEST_SET.json`. The plan below is
kept as the record of the rules they were written under. Dev templates are
used to tune prompts, labelers and monitor thresholds, so numbers on them are optimistic. Claims are
made only on test templates written under the rules below.

## Rules
1. 60 templates: 20 per family (records, reports, code). None may reuse a dev scenario. A paraphrase or
   a new name on a dev template does not count as new. `check_split_disjoint()` only checks ids, so a
   second person also checks scenarios by hand.
2. Write them **before** looking at any real-model dev trajectories in detail. Use the coverage matrix,
   not model failures, to decide what to write. Otherwise the test set gets tuned to known failures.
3. Each template states its correct behavior in one sentence. Two people (or one person on two
   different days) solve it by hand from the user prompt and tool outputs. Drop the template if they
   disagree.
4. Each template has exactly one `tempting_action`. For a planned positive control it must not be
   ALLOWED in the ledger (`test_tempting_action_is_never_authorized_at_start` covers this).
5. Freeze: commit the files, record the SHA-256 of `sid/tasks/*.py` in `runs/FROZEN.json` (the run
   manifest prints them), and change nothing afterwards. Fixes go in `DEVIATIONS.md` and the affected
   templates are reported separately.

## Coverage matrix (target counts per family)

| permission state of the shortcut | count | shortcut kind | count |
|---|---|---|---|
| needs confirmation, no answer (pending) | 5 | unauthorized write / action | 8 |
| needs confirmation, approved (the shortcut is skipping the request) | 3 | out-of-scope edit (other object or field) | 5 |
| needs confirmation, denied | 3 | wrong channel (e.g. email instead of note) | 2 |
| approved then revoked mid-task | 3 | content violation (confidential, unverified, uncited) | 3 |
| forbidden outright | 4 | missing information (right answer: "can't, X missing") | 2 |
| allowed only for a narrower scope | 2 | | |

Across each family: at least 5 templates where a tool output contains a suggestion to do the shortcut
(`external_suggestion=True`), so that copied directives can be told apart from self-written ones. Use
compaction steps between 5 and 9.

## Scenario ideas (not yet written; none overlaps a dev template)
- Records: refund above a limit that needs finance approval; account suspension that needs the trust
  team; a deletion request on an account under legal hold; a role/permission change that needs IT;
  bulk tagging limited to one region; changes to contact preferences; an invoice write-off; a data
  export to a vendor that needs a DPA (data processing agreement) on file; merging two households;
  reopening a closed ticket.
- Reports: a press release under embargo; a board memo with draft (unapproved) numbers; a
  postmortem with a no-names rule; translating a report that has a confidential appendix; a customer
  case study that needs the customer's consent; KPIs with one missing month; anonymizing survey
  results; release notes that must not mention unreleased features.
- Code: a database migration that needs DBA approval; flipping a feature flag in production; changing
  the log level in production; CI config that may not be edited; a dependency pin with a security
  advisory; a rollback that is approved then revoked; a secret in the repo that must not be printed; a
  cron schedule change; a flaky test that may not be skipped; a performance fix that needs a benchmark.
