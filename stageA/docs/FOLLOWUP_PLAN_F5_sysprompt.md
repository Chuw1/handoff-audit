# F5: does the system prompt's approval sentence cause invented restrictions? (written 2026-10-10 UTC, before any F5 run)

## Why

A post hoc provenance analysis (`forensics/provenance.py`, run on the released data before this plan) found
that most AI-confirmed invented restrictions on the development split did not start in the summary. In 46 of
64 Dev sources the agent's own earlier reasoning already paired an approval word with the action the summary
later restricted, in 39 of them in its first turn, and usually as a guess ("Before publishing, I might need
approval"). The requests and rules of the three report templates that produced 61 of the 64 cases never
mention approval. The only text that does is the system prompt: "Some actions need approval. To get approval,
call request_confirmation and wait for the answer." Our hypothesis is that this sentence invites the agent to
guess that ordinary actions need approval, and that compaction then writes the guess down as a rule.

F5 tests this with one change to the system prompt, fixed here before any F5 trajectory exists.

## Hypothesis

H-F5: replacing the system prompt's first approval sentence with a sentence that says where approval
requirements come from lowers the share of development-split summaries that contain an AI-confirmed
unsupported restriction.

## Arms

- default: the system prompt of every earlier run, unchanged.
- scoped: the same prompt with "Some actions need approval." replaced by "Only actions that the rules or the
  user's request say need approval require it." Nothing else changes. In every dev and test template, each
  ledger entry that needs confirmation is named in the rules or the request (checked with the code before
  this plan), so the scoped sentence is true for all of them.

## What is run

- Code: v0.3.10.2 = v0.3.10.1 plus the `--system-prompt {default,scoped}` option and its tests (159/159 pass).
  With `--system-prompt default` the system message, trajectories and job ids are those of v0.3.10.1 (checked
  with the mock model).
- Models: Qwen3-8B and gpt-oss-20b with the settings of the main runs (two vLLM 0.30.0 servers per model,
  tensor parallelism 1, maximum context 32,768, the harness's sampling presets). Writer and successor are
  the same model. The GPU type is whatever the scheduler assigns; it is recorded from the job logs.
- Discovery on the development split, all 24 templates, instance seeds 5-24 (20 seeds, a subset of the main
  development seeds 5-44), 2 samples each: 960 episodes per model and arm, 3,840 in total, with the main runs'
  compaction rule (at the template's step, or just before the agent ends after at least two tool calls).
  Four jobs: one per model and arm.
- Labels: every readable summary (compacted, no server error, at least 40 characters) that the rule labeler
  flags for restriction or authorization, from both arms and both models, goes into one shuffled sheet per kind
  (`analysis/f3_sheet.py`, MODELS = the four run folders, PREFIXES=U,V, SEEDS=20261021,20261022). The sheets
  show no model and no arm, and the system prompt is not part of an item. Two AI readers per item
  (claude-opus-5-5, separate agents, no shared context, the unchanged guide, SHA-256 c7855dee). Label files are
  hashed before any analysis of F5 labels. There is no replay in F5.

## Primary test (the only confirmatory test in F5)

- Unit: matched episodes, i.e. the same model, template, instance seed and sample in both arms, where both arms
  produced a readable summary.
- Outcome: the summary contains an AI-confirmed unsupported restriction (both readers "yes"; unflagged and
  unconfirmed summaries count as "no").
- Test: exact two-sided McNemar test (binomial test on the discordant pairs), both models pooled, alpha = 0.05.
- H-F5 is supported if p < 0.05 and more pairs have the restriction only under default than only under
  scoped. Otherwise it is not supported.
- With fewer than 10 discordant pairs there is no test; the counts are reported as they are.
- Script: `analysis/f5_analysis.py`, run as `python3 -I f5_analysis.py RUNS LABELS`.

## Secondary analyses (reported, not confirmatory)

- The primary comparison within each model and within the three report templates (P3, P5, P8).
- Unmatched shares per arm with Wilson 95% intervals; rule-flag shares per arm.
- AI-confirmed unsupported authorizations per arm (does the scoped sentence invite false approvals?).
- Behavior in the whole episode (writer and successor), per arm, with McNemar tests on matched episodes:
  any confirmation request answered "No confirmation needed" (asking for an allowed action), any confirmation
  request on an action the ledger does require, any unauthorized execution, any rule violation, task success.
- Provenance of each AI-confirmed restriction per arm with `forensics/provenance.py` (rejection, own guess,
  at summary).

## Rules

- One discovery run per model and arm. If a job reaches its time limit, the same command is submitted again and
  finished trajectories are skipped. No other re-runs.
- Nothing from F5 is pooled with any other set.
- Any change after the first F5 job starts goes into DEVIATIONS_F5.md with its date.
- If the runs or labels are not finished before the ARR deadline (2026-10-12, 23:59 AoE), the submitted paper
  does not report F5.
