# handoff-audit

When an LLM agent compacts its context, it replaces most of its history with a summary it writes itself.
This package tests two things about those handoff summaries: how often they state a permission or a
requirement that the task record does not support ("unsupported policy"), and whether such a sentence
changes what the agent does next. It is built to run on any model behind an OpenAI-compatible chat API with
tool calling (so far tested end to end only against scripted servers; see Limits), so it can be used as a benchmark (compare models on the same 60 held-out tasks) and as a diagnostic
(see which sentences a model invents and what they do), for example when a new model version comes out.

It is the code of a paper under anonymous review. AI assistants helped write parts of the code, as stated in
the submission's Responsible NLP checklist.

## Test your own model

You need Python 3.11 or later, `pip install -r requirements.txt` (the `openai` client, nothing else for the
diagnostic), the model under test behind a chat-completions endpoint that supports tool calling, and a
second model that reads the summaries.

1. Check the install. This needs no GPU, no model and no network (a few minutes):

   ```bash
   bash diagnose/selftest.sh
   ```

2. Run the diagnostic. The first argument is the model under test, the second the reader, the third a new
   output folder:

   ```bash
   export SID_API_KEY=...            # key for the model under test
   export READER_API_KEY=...         # key for the reader, if it is another provider
   bash diagnose.sh "api:<model-id>@<base-url>" "api:<reader-model-id>@<base-url>" out_mymodel
   ```

3. Read `out_mymodel/report.md` (numbers also in `out_mymodel/report.json`).

If the run stops (a rate limit, a closed laptop), run the same command again: finished episodes, labels and
replays are skipped. The labels are hashed before the replay starts (`labels/AI_LABELS_SHA256.txt`) and are not
changed after that.

### Model specs

| Where the model runs | Spec |
|---|---|
| OpenAI API | `api:<model-id>@https://api.openai.com/v1` |
| Gemini API (OpenAI compatibility) | `api:<model-id>@https://generativelanguage.googleapis.com/v1beta/openai/` |
| OpenRouter and other gateways | `api:<model-id>@https://openrouter.ai/api/v1` |
| Your own vLLM or SGLang server (open weights) | `openai:<served-name>@http://localhost:8000/v1` |

`api:` sends only standard chat-completions fields: no sampling values unless you set them
(`EXTRA_ARGS="--temperature 0.7"`), the token cap as `max_completion_tokens`, and none of the model's earlier
reasoning. If the provider says it does not support `seed`, `tool_choice` or that name of the token cap, the
client drops or renames it for the rest of the run and prints a note. A refused temperature or top-p stops
the run, because you set it. `openai:` is the client of the paper: it applies the sampling presets of
`stageA/sid/runner.py` (Qwen3, gpt-oss) and sends earlier reasoning back, as vLLM expects. Use it for open
weights you serve yourself.

### Options

Set them as environment variables before `bash diagnose.sh`:

| Variable | Default | Meaning |
|---|---|---|
| `SEED_OFFSET`, `SEEDS` | 5, 5 | instance seeds 5-9 of the 60 test templates (the seeds of the paper's F2 run) |
| `SAMPLES` | 2 | runs per instance; 4 gives the F2 design (1,200 episodes) |
| `REPLAYS` | 4 | successor runs per replay arm, as in the paper |
| `READER_B` | the reader | a different second reader (with one reader model, the two readers are two samples of it) |
| `READER_ARGS` | none | reader options, e.g. `"--max-tokens 16384"` for a reasoning model as reader |
| `WORKERS` | 4 | parallel requests; lower it if the provider rate-limits |
| `EXTRA_ARGS` | none | harness options for discovery and replay, e.g. `"--max-tokens 16384 --summary-max-tokens 16384"` for reasoning models, whose token cap includes the reasoning (the paper used 4,096) |
| `ALLOW_ERRORS` | 0 | 1 goes on although some episodes failed or some labels are unreadable (otherwise the run stops and a rerun retries them) |

### What it does

1. **Discovery.** The model works on 60 synthetic tool-use tasks (records, reports, code). Each task has a
   permission ledger that says which actions on which targets are allowed, forbidden or need confirmation. At
   a fixed step (in a few templates, right after an approval is withdrawn), or when the agent tries to finish
   after at least two tool calls, the harness asks it to write a summary; a fresh instance of the same model
   (the successor) continues from that summary only.
2. **Rule flags.** A rule labeler marks summary sentences that may state an approval or a requirement.
3. **Reading.** Two AI readers judge every flagged summary against the true permission state
   (`stageA/docs/AI_LABEL_GUIDE.md`). A sentence counts as unsupported policy only if both say yes.
4. **Replay.** For each confirmed summary, the successor is rerun from the same snapshot, four times per arm:
   summary as written; the sentences the readers marked replaced by neutral text; as many other sentences
   replaced (control); the marked sentences deleted; the marked sentences replaced by the true permission in
   the summary's words; the marked sentences replaced by a labelled statement of the permission record; the
   full history instead of a summary. Outcome: a confirmation request (restrictions) or an
   unauthorized action (authorizations).
5. **Report.** Shares of readable summaries with Wilson 95% intervals, reader agreement, the replay table with
   sign tests per source, and the paper's F2 numbers for Qwen3-8B and gpt-oss-20b for comparison.

### Cost

With the defaults, discovery is 600 episodes. In the paper's runs an episode took 7 to 10 model calls, about
9,000 to 10,000 prompt tokens and 1,500 to 3,000 completion tokens (Qwen3-8B and gpt-oss-20b); models that
reason at length use more. The readers make one call per flagged summary each. The replay makes about
7 arms x 4 runs successor episodes per confirmed summary, each shorter than a discovery episode.

### Limits

- `diagnose/ai_reader.py` automates the reading step with one model call per item. The paper's labels came
  from AI agents given the same guide (`analysis/READER_PROMPTS.md`); the agreement between the two has
  not been measured. Check a sample of items by hand (`labels/diag_*_sheet.txt` with `labels/ai_*.jsonl`), and
  prefer a reader from another model family than the model under test.
- Only rule-flagged summaries are read, and the rule labeler's recall is unknown, so the shares are lower bounds.
- The tasks are synthetic, compaction happens where the harness puts it, not where a product would, and the
  successor never sees the original request. The paper discusses what this means.
- Hosted APIs ignore or refuse seeds, so reruns differ. Results with `api:` and `openai:` are not strictly
  comparable, because `openai:` sends earlier reasoning back to the model and applies presets.
- The `api:` path has been tested only against scripted fake servers (`diagnose/selftest.sh`,
  `stageA/tests/test_v03103.py`); we have not yet run it against a hosted provider.

## Contents

```
diagnose.sh   the diagnostic for one model (steps above)
diagnose/     ai_reader.py (automated reader), targets.py (agreement, confirmed sources, replay targets),
              report.py, selftest.sh and fake_api.py (check without a model)
stageA/       experiment harness v0.3.10.3: tasks, permission ledger, agent loop with compaction,
              rule labeler, same-snapshot replay, run scripts, 165 tests, Slurm job script
annotation/   annotation_v04.py: builds the reader items (request, rules, permission state, numbered
              summary, approval-related history lines) used by the sheet scripts
analysis/     sheet builders, label merging and replay target files, every statistic reported in the paper,
              figures; reproduce.sh runs them; READER_PROMPTS.md has the exact task message of every AI reader
forensics/    provenance.py: where each confirmed unsupported sentence came from (post hoc)
LICENSE       MIT
```

`stageA/README.md` describes the harness in detail. `stageA/docs/FROZEN_TEST_SET.json` fingerprints the 60
test templates, and `python3 stageA/scripts/freeze_test_set.py --verify` recomputes every test instance and
compares it with that file (the specification it hashes, `docs/TEST_SET_DRAFT_zh.md`, is written in Chinese).

# Reproducing the paper

## Code versions

This repository holds harness v0.3.10.3. The paper's supplementary code archive holds v0.3.10.2, which the F5
runs used: v0.3.10.1 (used by the F1, F2, F4 and scale-check runs) plus `--system-prompt {default,scoped}` for
the follow-up F5 (`stageA/docs/FOLLOWUP_PLAN_F5_sysprompt.md`, with `analysis/f5_analysis.py` and
`forensics/provenance.py`, all written before any F5 run). v0.3.10.3 adds the `api:` model spec, `diagnose/` and `diagnose.sh`. With the default
settings and a `vllm:` or `openai:` spec, both versions send the same requests and give the same job ids as
v0.3.10.1. The development and test runs used v0.3.10. In code, v0.3.10.1 differs only in `scripts/run_replay.py`, `sid/replay.py`, `scripts/selfcheck.py`
and the new `tests/test_v03101.py` (replay of an explicit list of target sentences and the `neutral_control`
arm); it also adds the plans and the reader guide to `docs/`. The earlier
development batch in `data/r039/` used older versions (see the data README). Run manifests record the SHA-256 of every source file. For
files whose released copy is anonymized (for example `sid/llm.py`, the Slurm scripts, `PROTOCOL.md`)
the recorded hash is replaced by `withheld-for-review`, and so is the code-tree hash; the original values will be
given with the final version. Some documents in `stageA/` mention files that are not included: job-submission
scripts and a GPU check for our cluster, internal notes and result summaries (in Chinese), and the bilingual guide
for the sentence-level workbooks that `annotation_v04.py` builds (the human check in the paper uses the AI reader
guide, `stageA/docs/AI_LABEL_GUIDE.md`). Several documents in `stageA/` and the plan files use "pre-registered" loosely; the paper calls the test pre-specified,
because the plan was not filed with a public registry.

## Requirements

- Harness and analyses: Python 3.11 or later, standard library only, plus `openai` (tested with 3.22.1) to
  talk to a vLLM server. Figures need `matplotlib` and `numpy`. The workbook functions in
  `annotation/annotation_v04.py` need `openpyxl`. That module imports the harness, so run it with
  `PYTHONPATH=stageA` if you use it on its own (the analysis scripts set the path themselves); its workbook
  labels are in Chinese and English.
- Experiments in the paper: vLLM 0.30.0 (CUDA 12.9 build) on NVIDIA H100 80GB GPUs (one discovery run of the
  earlier development batch, both F4 discovery runs and the F4 Qwen3-8B replay ran on H200 nodes). Two servers with tensor parallelism 1 per model;
  gpt-oss-120b one server with tensor parallelism 2; Qwen3-235B-A22B-FP8 one server on four GPUs. Weights come unchanged
  from Hugging Face; the manifests record these commits:

  | Model | Hugging Face commit |
  |---|---|
  | Qwen/Qwen3-8B | b968826d9c46dd6066d109eabc6255188de91218 |
  | Qwen/Qwen3-14B | 40c069824f4251a91eefaf281ebe4c544efd3e18 |
  | openai/gpt-oss-20b | 6cee5e81ee83917806bbde320786a8fb61efebee |
  | openai/gpt-oss-120b | b5c939de8f754692c1647ca79fbf85e8c1e70f8a |
  | Qwen/Qwen3-235B-A22B-FP8 | 39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35 |

  Sampling settings are in `stageA/sid/runner.py` (`PRESETS`) and in Appendix B of the paper.

## Quick check without a GPU

```bash
cd stageA
python3 scripts/selfcheck.py                 # 165 tests; 11 of them need the openai package
python3 scripts/freeze_test_set.py --verify  # test instances unchanged
python3 scripts/run_discovery.py --model mock:self_authorize --seeds 2 --samples 2 --out runs/mock_disc
python3 scripts/run_replay.py --model mock:self_authorize --from runs/mock_disc/trajectories.jsonl --replays 2 --out runs/mock_replay
```

The mock policies only show that the machinery works; their numbers say nothing about real models.

## Running the experiments

`stageA/slurm/stageA.sbatch` starts one or more vLLM servers on a node, waits until they serve the model,
runs up to six scripts against them, and stops the servers. Set `--account` and `--partition` for your
cluster. Before a test-split run:

- record the code version: put the SHA-256 of the archive in `stageA/ARCHIVE_SHA256.txt` (or make the
  folder a git repository with a commit); test-split runs refuse to start without one;
- put the Hugging Face commit of the weights in `$MODEL_DIR/REVISION` if the model folder has no download
  metadata;
- for a replay with `--targets-file`, copy the target file (from `data/*/targets/`) into `stageA/`.

Example, the F2 discovery run for one model:

```bash
sbatch --export=ALL,MODEL_DIR=$HOME/models/Qwen3-8B,SERVED_NAME=Qwen/Qwen3-8B,TP=1,\
STAGE="scripts/run_discovery.py --split test --seed-offset 5 --seeds 5 --samples 4 --out runs/test_disc_f2_qwen3_8b" \
slurm/stageA.sbatch
```

and its replay:

```bash
STAGE="scripts/run_replay.py --split test --from runs/test_disc_f2_qwen3_8b/trajectories.jsonl \
  --targets-file targets_f2_qwen3_8b.json \
  --arms original neutral neutral_control delete claim_correct ledger_correct --replays 4 \
  --out runs/test_replay_f2_qwen3_8b"
```

Every script writes a `manifest_*.json` with its arguments, the serving settings and source hashes, and
appends one JSON row per episode, so an interrupted job can be resubmitted.

## Reproducing the reported numbers

The run records and labels are in the data archive of the paper's supplementary material. Unpack it, then:

```bash
bash analysis/reproduce.sh "$PWD" /path/to/data /tmp/new_out_dir /path/to/data/outputs
```

The output folder must not exist yet. The script recomputes every analysis from the run records and labels,
rebuilds all AI-reader sheets (Dev, Test, compaction prompts, F2, F3, F3c, F4, F5) from the run records and compares
them byte for byte with the released sheets, rebuilds the F2, F3, F3c and F4 replay target files, draws the
figures, and compares each recomputed analysis with the copy in `data/outputs/`. It exits with a non-zero
status if anything differs or fails. On our copy everything matches.

The F1 target files list, for each test source that both readers labeled yes, all sentences either reader
marked. `f3_targets.py` with `TAG=test` on the test labels gives the same sentences; in our files two
gpt-oss-20b sources that the test key lists under both kinds carry only the authorization type, the sheet
in which they were read.

| Paper item | Script |
|---|---|
| Prevalence (Table 2), rule-flag rates | `discovery_counts.py`, `f2_targets.py`, `f2_extra.py`, `f3_targets.py` |
| Restriction replays, all sets (Table 4) | `dev_replay_tables.py`, `test_analysis.py`, `tf_analysis.py`, `allsets.py` |
| Invented vs. overgeneralized restrictions, what successors asked about | `grounded.py`, `mechanism.py` |
| Cluster bootstrap intervals (Figure 2) | `boot.py`, `fig_forest.py` |
| Per-arm rates (Figure 3), repairs, authorizations | `allsets.py`, `fig_arms.py` |
| Per-template table | `tab_templates.py` |
| Compaction prompts | `compaction_prompts.py`, `discovery_counts.py` |
| Cross-model handoff, positive control, monitors | `cross_model.py`, `positive_control.py`, `monitor_auroc.py` |
| When compaction happened, by set, kind and model (Section 5.4, Table 5, Appendix E) | `compaction_trigger.py` |
| Reader agreement (kappa) for every set | `agreement.py` |
| Human check: author vs. AI readers, and the planned sensitivity check (Sections 3 and 5.3) | `hc_agreement.py` |
| Seed reproducibility, Test vs. F1 (Appendix B) | `reproducibility.py` |
| Scale checks, gpt-oss-120b and Qwen3-235B (Appendix F) | `f3_sheet.py`, `f3_targets.py`, `f3_analysis.py`, `f3_posthoc.py`, `scale_prevalence.py` |
| F4, pre-specified check of the step finding (Section 5.4, Table 5, Appendix G) | `f3_sheet.py`, `f3_targets.py`, `f4_primary.py` (the script fixed in the F4 plan, unchanged), `f4_extra.py` |
| F5, the system prompt's approval sentence (Section 5.6, Table 15, Appendix H) | `f3_sheet.py`, `f5_analysis.py` (the script fixed in the F5 plan, unchanged), `f5_provenance.py` (the classes of `forensics/provenance.py`, adapted to the F5 runs; not hashed in advance), `f5_agreement.py`, `f5_cluster.py` (post hoc: how the result depends on templates) |
| Where unsupported policy came from (provenance trace; Section 5.6, Appendix H) | `../forensics/provenance.py` |
| Study-design figure (Figure 1) | `fig_pipeline.py` |

## How the AI labels were made

A sheet script writes each candidate summary as one item, in a fixed random order, without the model name
or any outcome. Which summaries become items differs by set: Dev, a random sample of the restriction flags
and every authorization flag among the replayed sources; Test, every replayed source (restriction sources
replayed from the flags, authorization sources plus unflagged controls); compaction prompts, F2, F3, F3c and F4,
every rule-flagged summary. Two AI readers (separate agents with no shared context) receive the guide
and a short task message (`READER_PROMPTS.md`, exact text per set). Readers a and b read the same items and
readers c and d read the same items (the other half of the set, or for the compaction-prompt runs the
brief-prompt sheets), so every item has two independent labels. Rule-labeler flags are shown as starred
sentences. The label files are hashed in `*_AI_LABELS_SHA256.txt`; for F2, F3, F3c and F4 this happened before
the replay was submitted, while the Dev and Test replays, which edited rule-flagged sentences, had already run.
`f2_targets.py` and `f3_targets.py` compute agreement, keep items that both readers label "yes", and write
the replay target file.

## Anonymization

Cluster account names, user paths, node and cluster names, cluster-specific notes (billing, queues), one
author name and one plan hash were replaced or removed in the harness comments, the Slurm scripts and the
documentation. Internal notes were left out. The synthetic tasks use common street names with real city
names for customer addresses; they are part of the frozen test set and were not changed.
