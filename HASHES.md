# SHA-256 values named in the paper

The appendices of the paper say that certain files were written and hashed before the runs they
govern. This file gives the full SHA-256 of each of those files and says where the value is recorded.

Where the files are:

- **repo**: this repository (paths from the repository root).
- **code archive**: `sid_code_v21.zip` in the GitHub release (it unpacks to `code/`).
- **data archive**: `sid_data_v20.tgz` in the GitHub release (it unpacks to `data/`).
- **F3b archive**: `sid_data_f3b.tgz` in the GitHub release (it unpacks to `data_f3b/`; the F3b Kimi K2.6 check).

Check any file with `sha256sum <file>` and compare the result with the value below.

## Release archives

| Archive | SHA-256 |
|---|---|
| `sid_code_v21.zip` | `90a203df0e889488324687651afefde888f302b4f13d0aafa2eed3aeb1f5df48` |
| `sid_data_v20.tgz` | `9399be874dbbd7165d8ffc02b4b6e395ba717d510cc2602c5c3e0957d4dd8a40` |
| `sid_data_f3b.tgz` | `2f7f44b74f7c6bdf323b1f91c4b5aa5ae21c72a606d9342cbe1eb5205472b2af` |

## The 13 files

| # | Paper | File | SHA-256 | Copies with this hash |
|---|---|---|---|---|
| 1 | App. C | AI reader guide `AI_LABEL_GUIDE.md` | `c7855dee4c5232399ca38c1534dd8d697a18d33cfa4a5026082a075a31d629e6` | repo `stageA/docs/`; code archive `code/stageA/docs/`; data archive `data/{ov310,test310,f1f2,h3,f3,f3c,f4,f5,f6}/labels/` |
| 2 | App. D | frozen test split `FROZEN_TEST_SET.json` | `bd7890f38fce71c1dea8fe37b64331d81c3fac0de1abf6f050d0d0595ec8ba7f` | repo `stageA/docs/`; code archive `code/stageA/docs/` |
| 3 | App. D | test plan `TEST_PLAN_v0310.md` (copy released for review) | `4d9321b8cbd864444c709cb5841559d6b7f9432a2ed65f71ce2ec7e8493aab5c` | repo `stageA/docs/`; code archive `code/stageA/docs/`; data archive `data/plans/` |
| 4 | App. D | follow-up plan `FOLLOWUP_PLAN_v03101.md` (copy released for review) | `a395cdbf4b0ee9e1e6754a7832e48ee99bde8232b8e6a1af0354596bc34e114c` | repo `stageA/docs/`; code archive `code/stageA/docs/`; data archive `data/plans/` |
| 5 | App. F | F3 plan `FOLLOWUP_PLAN_F3_scale.md` | `1cd7540a0b494bc0e4bd076a227c00322695f29160cef59f7188911cf4b73290` | data archive `data/plans/` |
| 6 | App. G | F4 plan `FOLLOWUP_PLAN_F4_step.md` | `d7c04015e8161b4d37cc1fc223779908ac3f77a1c14aee9e8da837a49ceb1178` | data archive `data/plans/` |
| 7 | App. G | F4 analysis script `f4_primary.py` | `53c63d4d06a18460cc902a54e4007f145f9b5738652cea2fbcdf4d0be3895a79` | repo `analysis/`; code archive `code/analysis/` |
| 8 | App. H | F5 plan `FOLLOWUP_PLAN_F5_sysprompt.md` | `b6f042657cb301b44879d490653b67a00ff5fed8a8294e9d26c8d8e837a63346` | repo `stageA/docs/`; code archive `code/stageA/docs/`; data archive `data/plans/` |
| 9 | App. H | F5 analysis script `f5_analysis.py` | `8c9b215f1bc939d481f890c7752b06528c1e378a695cbb1e27521c007ce4c2e8` | repo `analysis/`; code archive `code/analysis/` |
| 10 | App. H | F5 provenance script `provenance.py` | `cddc2d916dd5a42289cda823efef1e633a23a423aa2cdff3f2531756348c7618` | repo `forensics/`; code archive `code/forensics/` |
| 11 | App. H | F6 plan `FOLLOWUP_PLAN_F6_heldout.md` | `df53f27b597a20842b2581574bc6e3c95036a7c1d1aa3bb93830e9b827c0c752` | repo `stageA/docs/`; code archive `code/stageA/docs/`; data archive `data/plans/` |
| 12 | App. H | F6 analysis script `f6_analysis.py` | `c83518f35a763fe81b17e2608d921d3c0efa34bf4ec96aa3660b7bf5c2d601d5` | repo `analysis/`; code archive `code/analysis/` |
| 13 | App. H | F6 provenance script `f6_provenance.py` | `5039b85adfebeeb6069036886eed06d4e8dd081eeeef70ca8080e3c39674d626` | repo `analysis/`; code archive `code/analysis/` |

## Where each value is recorded

1. **AI reader guide.** Listed in these 13 hash files of the data archive (the other label hash files,
   `data/ov310/labels/AI_LABELS_SHA256.txt` and `data/test310/labels/human/HUMAN_LABELS_SHA256.txt`, do not list it):
   `data/test310/labels/TEST_AI_LABELS_SHA256.txt` (time written in the file: Wed Oct  7 13:18:08 UTC 2026),
   `data/f1f2/labels/F2_AI_LABELS_SHA256.txt` and `data/f2r2/raw/F2_AI_LABELS_SHA256.txt` (Wed Oct  7 17:20:23 UTC 2026),
   `data/h3/labels/H3_AI_LABELS_SHA256.txt` (Wed Oct  7 22:26:08 UTC 2026),
   `data/f3/labels/F3_AI_LABELS_SHA256.txt` (frozen: Thu Oct  8 01:40:16 UTC 2026), `data/f3/labels/F3_SHEETS_SHA256.txt` (no time),
   `data/f3c/labels/F3C_AI_LABELS_SHA256.txt` (frozen: Thu Oct  8 13:16:16 UTC 2026), `data/f3c/labels/F3C_SHEETS_SHA256.txt` (no time),
   `data/f4/labels/F4_SHEETS_SHA256.txt` (hashed 2026-10-10T01:12:28Z),
   `data/f4/labels/F4_AI_LABELS_SHA256.txt` and `data/f4r2/raw/F4_AI_LABELS_SHA256.txt` (frozen: Sat Oct 10 01:19:59 UTC 2026),
   `data/f5/labels/F5_AI_LABELS_SHA256.txt` (frozen: Sat Oct 10 18:35:50 UTC 2026),
   `data/f6/labels/F6_AI_LABELS_SHA256.txt` (frozen: Mon Oct 12 12:42:41 UTC 2026).
   Also written in full in the F4 plan, `data/plans/FOLLOWUP_PLAN_F4_step.md` (plan header: written 2026-10-09 UTC),
   and in shortened form (`c7855dee…d629e6`) in the test plan `TEST_PLAN_v0310.md`.
2. **Frozen test split.** `stageA/docs/ARCHIVE_HASHES.md` (repo and code archive; the file says the split was frozen
   2026-10-01 and checked in each code archive on 2026-10-02). Also recorded in 61 of the 64 run manifests
   (`manifest_*.json`) in the data archive, under `source_sha256["docs/FROZEN_TEST_SET.json"]` and
   `code.frozen_test_set_sha256`; for example
   `data/f6/raw/runs/test_disc_f6_scoped_qwen3_8b/manifest_20261011_171746.json` ("time": 2026-10-11T17:17:46-0400).
   The 3 manifests without it are those of the runs in `data/r039/runs/disc_v03_*`.
   Shortened form (`bd7890f3…ec8ba7f`) in the test plan `TEST_PLAN_v0310.md`.
3. **Test plan.** `data/plans/PLAN_HASHES.md` gives this value for the copy released for review and says that one author
   name and the cluster node names were replaced. The SHA-256 recorded before the runs for the file as written is
   **not available** in the archives or the repository.
4. **Follow-up plan.** `data/plans/PLAN_HASHES.md` gives this value for the copy released for review and says that one
   author name was replaced. The SHA-256 recorded before the runs for the file as written is **not available** in the
   archives or the repository.
5. **F3 plan.** `data/plans/PLAN_HASHES.md` (marked "same as written: yes"). The plan header says it was written
   2026-10-08, before any F3 run. The archives give no time of hashing for this plan (the F3 row of the table in
   `data/README.md`, line 70, gives none). The value is also quoted in shortened form in two later plans:
   `data/plans/FOLLOWUP_PLAN_F3b_kimi.md` line 5 ("F3 (docs/FOLLOWUP_PLAN_F3_scale.md, SHA-256 1cd7540a...)") and
   `data/plans/FOLLOWUP_PLAN_F3c_amend.md` line 3 ("plan SHA-256 1cd7540a...").
6. **F4 plan.** `data/plans/PLAN_HASHES.md` (marked "same as written: yes"). The plan header says it was written
   2026-10-09 UTC, before any F4 run. The time of hashing is recorded in `data/README.md` line 74, in the table of
   times recorded in the hash files: "F4 (plan hashed Oct 9, 02:24)". Line 57 introduces that table as "UTC start times
   of the scripts, from the run manifests, and the times recorded in the hash files."
7. **F4 analysis script.** Written in full in the F4 plan, `data/plans/FOLLOWUP_PLAN_F4_step.md` (line 50). Also in
   shortened form in `data/plans/DEVIATIONS_F4.md` line 13: "the analysis script `analysis/f4_primary.py` (SHA-256
   prefix 53c63d4d) unchanged".
8. **F5 plan**, 9. **F5 analysis script**, 10. **F5 provenance script.** `data/f5/F5_HASHES.txt`, which ends with
   "hashed 2026-10-10T16:44:42Z, before any F5 run". The F5 plan is also in `data/plans/PLAN_HASHES.md`.
   Also recorded in `data/plans/DEVIATIONS_F5.md` line 1 ("SHA-256 b6f04265...") and line 5 ("2026-10-10 16:44 | plan,
   `f5_analysis.py` (8c9b215f...) and `provenance.py` (cddc2d91...) hashed, before any F5 run"), and in `data/README.md`
   line 75 ("F5 (plan and scripts hashed Oct 10, 16:44)").
11. **F6 plan**, 12. **F6 analysis script**, 13. **F6 provenance script.** `data/f6/F6_HASHES.txt` (the same file is in
    the repo as `stageA/docs/F6_HASHES.txt`), which ends with "hashed 2026-10-11T19:08:44Z, before any F6 run".
    The F6 plan is also in `data/plans/PLAN_HASHES.md`. Also recorded in `data/plans/DEVIATIONS_F6.md` line 1
    ("SHA-256 df53f27b...") and line 5 ("2026-10-11 19:08 | plan, `f6_analysis.py` (c83518f3...) and `f6_provenance.py`
    (5039b85a...) hashed, before any F6 run (`F6_HASHES.txt`)"), and in `data/README.md` line 76 ("F6 (plan and scripts
    hashed Oct 11, 19:08)").

## Other hash records in the archives

- `data/plans/PLAN_HASHES.md`: all eight plan files, including the Kimi K2.6 plan (F3b) and the Qwen3-235B amendment (F3c),
  with what was replaced in each copy released for review.
- `data/f5/F5_HASHES.txt` and `data/f6/F6_HASHES.txt`: also give the code archive used for F5 and F6 (`stageA_v0.3.10.2.zip`).
- `data/f6/raw/ARCHIVE_SHA256.txt`: only the SHA-256 of that code archive, `stageA_v0.3.10.2.zip`.
- `stageA/docs/ARCHIVE_HASHES.md` (repo and code archive): the code archives used during the study.
- Label and sheet hash files: `data/*/labels/*_SHA256.txt`, `data/f2r2/raw/F2_AI_LABELS_SHA256.txt`,
  `data/f4r2/raw/F4_AI_LABELS_SHA256.txt`, `data/ov310/labels/AI_LABELS_SHA256.txt`, and for the human check
  `data/test310/labels/human/HUMAN_LABELS_SHA256.txt`.
- `data/f4/raw/F4_DISC_SHA256.txt`: the F4 discovery trajectory files.
- `data/README.md` (section "Order of events"): a table of the times recorded in the hash files.

## F3b (Kimi K2.6), added after the review archives

`sid_data_f3b.tgz` in the GitHub Release unpacks to `data_f3b/`. Its label hash files were written on November 3, 2026,
before agreement, prevalence or replay targets were computed (`data_f3b/DEVIATIONS_F3b.md`).

| File | SHA-256 | Where the value is recorded |
|---|---|---|
| `data_f3b/labels/F3B_AI_LABELS_SHA256.txt` (the four label files, the guide, the two sheets and the two keys; ends "frozen: Tue Nov  3 18:17:06 UTC 2026") | `3e873d513a829b5fdf25f80d08dfba79399eac9b95695d4eede03ac25a630754` | `data_f3b/REPLAY_COMMAND.md` lines 22 and 35 |
| `data_f3b/labels/F3B_SHEETS_SHA256.txt` (the guide, the two sheets and the two keys, before any reader started; ends "frozen: Tue Nov  3 18:06:36 UTC 2026") | `22ee03b4dff302bbc5fe7a8f982e9cba364e4b41549bdf79c3b445c4ef5fb9de` | not recorded elsewhere |
| `data_f3b/targets/targets_f3b_kimi_k2_6.json` (replay targets) | `333bb5bcf6e379c12b31fa46cd4103419913b847ec4832a3f924684aeacef892` | `data_f3b/REPLAY_COMMAND.md` lines 21 and 35; also recorded in `data_f3b/targets/f3b_targets.txt` line 6 |
| `data_f3b/raw/runs/test_disc_f3b_kimi_k2_6/trajectories.jsonl` (discovery run) | `9db9461deeb6c0fe26f58105f4b47646a95ccb152b2b6dddcbb96ba392a327b0` | `data_f3b/REPLAY_COMMAND.md` line 55 |

The AI reader guide in `data_f3b/labels/AI_LABEL_GUIDE.md` is the same file as item 1
(`c7855dee4c5232399ca38c1534dd8d697a18d33cfa4a5026082a075a31d629e6`); both F3b hash files list it.

All times come from the files themselves. They are not certified by a third party.
