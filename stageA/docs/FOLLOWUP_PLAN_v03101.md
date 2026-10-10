# Follow-up plan after the test-split primary test (written 2026-10-07, before any follow-up run)

## Why there is a follow-up

The pre-registered primary test in `docs/TEST_PLAN_v0310.md` did not reject the null: for 37 AI-confirmed
unsupported-restriction sources, confirmation requests were 126/148 (original) vs 119/148 (neutral), sign test
8 down / 5 up, p = 0.58. That result stands and is reported as the primary test-split result. After seeing it we
found (post hoc) that in 24 of the 37 sources the readers had marked unsupported sentences that the replay did
not edit, because replay targets came from the rule labeler, not from the readers. The follow-up tests the
hypothesis that motivated the study with that design flaw removed. It is a new experiment, decided after the
primary result, and is reported as such.

## Code

v0.3.10.1 = v0.3.10 plus two additions, nothing else changed (`DEVIATIONS.md`):
- `run_replay.py --targets-file`: replay exactly the listed summaries with the listed sentences edited.
- arm `neutral_control`: replaces as many unmarked sentences as `neutral` replaces, each matched in word count
  to one marked sentence, with the same neutral filler. It is the negative control for `neutral`.

## F1 (exploratory): all marked sentences, existing test sources

The 52 AI-confirmed test sources (37 restriction, 15 authorization; 21 Qwen3-8B, 31 gpt-oss-20b). Targets = the
union of the sentences both readers marked (labels frozen 2026-10-07 13:18 UTC). Arms: original, neutral,
neutral_control, delete, claim_correct, ledger_correct, no_compaction; K = 4. Because the original-arm outcomes
of these sources are already known, F1 is exploratory only.

## F2 (confirmatory follow-up): fresh instances of the test templates

- Discovery on the 60 test templates with instance seeds 5–9 (never run before), 4 samples each: 1,200
  trajectories per model, Qwen3-8B and gpt-oss-20b, H100 only, code v0.3.10.1.
- Every summary the rule labeler flags for restriction or authorization is read by two AI readers with the
  unchanged guide (`docs/AI_LABEL_GUIDE.md`, SHA-256 `c7855dee…`), blind to model and outcomes. Labels are hashed
  before any F2 replay is submitted.
- Replay set: every source that both readers label "yes"; targets = union of both readers' marked sentences.
  Arms as in F1, K = 4.
- **Primary (F2):** AI-confirmed restriction sources pooled over both models; per-source share of runs with at
  least one confirmation request, original minus neutral; exact two-sided sign test, alpha = 0.05.
- Reported with it: neutral_control (negative control, expected no change), delete, each model separately, a
  sign test over (model, template) cells, claim_correct and ledger_correct as oracle probes, no_compaction as the
  descriptive hand-off increment. Authorization sources: unauthorized execution and confirmation requests,
  reported as secondary.
- If time allows, one author reads a random 30 F2 items blind as a human check.
