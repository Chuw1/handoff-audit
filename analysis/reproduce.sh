#!/bin/bash
# Recompute every analysis output from the released code and data, rebuild the AI-reader sheets and replay
# target files, draw the figures, and compare with the released copies.
# usage: bash reproduce.sh CODE_DIR DATA_DIR OUT_DIR [REF_DIR]
#   CODE_DIR  the unpacked code archive (the folder with stageA/, annotation/, analysis/)
#   DATA_DIR  the unpacked data archive
#   OUT_DIR   a folder that does not exist yet
#   REF_DIR   optional; usually DATA_DIR/outputs
# Exit status: 0 if every step ran and every comparison matched, 1 otherwise.
set -u
if [ $# -lt 3 ]; then echo "usage: bash reproduce.sh CODE_DIR DATA_DIR OUT_DIR [REF_DIR]"; exit 2; fi
C=$1; D=$2; O=$3; REF=${4:-}
if [ -e "$O" ]; then echo "OUT_DIR $O exists; give a new folder"; exit 2; fi
mkdir -p "$O" || exit 2
A=$C/analysis; SID=$C/stageA; ANN=$C/annotation
PY="python3 -I -B"
BAD=0
run() { name=$1; shift; echo "--- $name"; if ! "$@" > "$O/$name" 2> "$O/$name.err"; then echo "    FAILED (see $name.err)"; BAD=1; fi; }
same() { if cmp -s "$1" "$2"; then echo "identical: $3"; else echo "DIFFERS: $3"; BAD=1; fi; }

# discovery counts (prevalence of rule flags)
run disc_dev.txt env CODE="$SID" $PY "$A/discovery_counts.py" "$D"/ov310/raw/runs/disc_v039x_{qwen3_8b,gptoss_20b,qwen3_14b}/trajectories.jsonl "$D"/ov310/raw/runs/disc_h3{s,b}_{qwen3_8b,gptoss_20b}/trajectories.jsonl
run disc_test.txt env CODE="$SID" $PY "$A/discovery_counts.py" "$D"/test310/raw/runs/test_disc_v0310_{qwen3_8b,gptoss_20b}/trajectories.jsonl
# development replays, positive control, cross-model handoff, monitors, compaction prompts
run dev_replay_tables.txt env RUNS="$D/ov310/raw/runs" LAB="$D/ov310/labels" $PY "$A/dev_replay_tables.py"
run positive_control.txt env RUNS="$D/ov310/raw/runs" $PY "$A/positive_control.py"
run cross_model.txt env S="$D" $PY "$A/cross_model.py"
run monitor_auroc.txt $PY "$A/monitor_auroc.py" "$D/ov310/raw/runs/mon_gptoss_20b_on_qwen3/monitor_scores.jsonl" "$D/ov310/raw/runs/mon_qwen3_8b_on_gptoss_20b/monitor_scores.jsonl"
run compaction_prompts.txt $PY "$A/compaction_prompts.py" "$D"
# pre-specified test split
run test_analysis.txt env RUNS="$D/test310/raw/runs" LAB="$D/test310/labels" $PY "$A/test_analysis.py"
# follow-ups F1, F2 and pooled analyses
run f1_analysis.txt $PY "$A/tf_analysis.py" "$D/f1f2/raw/runs" f1 "$D/f1f2/targets" "$D/test310/raw/runs"
run f2_analysis.txt $PY "$A/tf_analysis.py" "$D/f2r2/raw/runs" f2 "$D/f1f2/targets"
run f2_extra.txt $PY "$A/f2_extra.py" "$D"
run grounded.txt $PY "$A/grounded.py" "$D"
run mechanism.txt $PY "$A/mechanism.py" "$D"
run compaction_trigger.txt $PY "$A/compaction_trigger.py" "$D"
run agreement.txt $PY "$A/agreement.py" "$D"
run reproducibility.txt $PY "$A/reproducibility.py" "$D"
run hc_agreement.txt $PY "$A/hc_agreement.py" "$D/test310/labels" "$D/test310/labels/human/human_author.jsonl" "$D/test310/raw/runs"
run scale_prevalence.txt $PY "$A/scale_prevalence.py" "$D"
run allsets.stdout $PY "$A/allsets.py" "$D" "$O/allsets.json"
run boot.stdout $PY "$A/boot.py" "$D" "$O/boot.json"
run tab_templates.stdout $PY "$A/tab_templates.py" "$D" "$O/tab_templates.tex"
# AI-reader sheets: Dev, Test, compaction prompts
run dev_restr_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/ov310/raw/runs" OUT="$O/dev_restr" $PY "$A/dev_restr_sheet.py"
run dev_auth_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/ov310/raw/runs" OUT="$O/dev_auth" $PY "$A/dev_auth_sheet.py"
run test_auth_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/test310/raw/runs" KIND=auth PREFIX=U SEED=20261008 OUT="$O/test_auth" $PY "$A/test_sheet.py"
run test_restr_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/test310/raw/runs" KIND=restr PREFIX=V SEED=20261009 OUT="$O/test_restr" $PY "$A/test_sheet.py"
for v in s b; do
  run h3${v}_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/ov310/raw/runs" OUT="$O/h3$v" DISC="disc_h3${v}_{m}" MODELS=qwen3_8b,gptoss_20b PREFIXES=U,V SEEDS=20261011,20261012 $PY "$A/f3_sheet.py"
done
# F2 sheets and targets from discovery + labels
run f2_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/f1f2/raw/runs" OUT="$O/f2" $PY "$A/f2_sheet.py"
run f2_targets.txt $PY "$A/f2_targets.py" "$D/f1f2/labels" "$O"
# scale checks
run f3_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/f3/raw/runs" OUT="$O/f3" MODELS=gptoss_120b PREFIXES=U,V SEEDS=20261013,20261014 $PY "$A/f3_sheet.py"
run f3_targets.txt env MODELS=gptoss_120b TAG=f3 PREFIXES=U,V $PY "$A/f3_targets.py" "$D/f3/labels" "$O"
run f3_analysis.txt env MODELS=gptoss_120b RESTORE=1 $PY "$A/f3_analysis.py" "$D/f3r2/raw/runs" f3 "$D/f3/targets"
run f3_posthoc.txt $PY "$A/f3_posthoc.py" "$D" "$D/f3/labels" f3 gptoss_120b "$D/f3/raw/runs/test_disc_f3_gptoss_120b/trajectories.jsonl" "$D/f3r2/raw/runs/test_replay_f3_gptoss_120b/replay.jsonl"
run f3c_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/f3c/raw/runs" OUT="$O/f3c" DISC='test_disc_f3c_{m}' MODELS=qwen3_235b PREFIXES=U,V SEEDS=20261015,20261016 $PY "$A/f3_sheet.py"
run f3c_targets.txt env MODELS=qwen3_235b TAG=f3c PREFIXES=U,V $PY "$A/f3_targets.py" "$D/f3c/labels" "$O"
run screen_qwen3_235b.txt $PY "$SID/scripts/check_screen.py" "$D/f3c/raw/runs/screen_qwen3_235b"
run f3c_analysis.txt env MODELS=qwen3_235b RESTORE=1 $PY "$A/f3_analysis.py" "$D/f3cr2/raw/runs" f3c "$D/f3c/targets"
run f3c_posthoc.txt $PY "$A/f3_posthoc.py" "$D" "$D/f3c/labels" f3c qwen3_235b "$D/f3c/raw/runs/test_disc_f3c_qwen3_235b/trajectories.jsonl" "$D/f3cr2/raw/runs/test_replay_f3c_qwen3_235b/replay.jsonl"
# pre-specified check of the step finding (F4): sheets, targets, the planned test, extra numbers
run f4_sheet.stdout env CODE="$SID" ANN="$ANN" RUNS="$D/f4/raw/runs" OUT="$O/f4" DISC='test_disc_f4_{m}' MODELS=qwen3_8b,gptoss_20b PREFIXES=U,V SEEDS=20261019,20261020 $PY "$A/f3_sheet.py"
run f4_targets.txt env MODELS=qwen3_8b,gptoss_20b TAG=f4 PREFIXES=U,V $PY "$A/f3_targets.py" "$D/f4/labels" "$O"
run f4_primary.txt $PY "$A/f4_primary.py" "$D/f4r2/raw/runs" f4 "$D/f4/targets" "$D/f4/raw/runs"
run f4_extra.txt $PY "$A/f4_extra.py" "$D"
# figures (drawn, not compared: PDF files carry creation dates)
run fig_pipeline.stdout $PY "$A/fig_pipeline.py" "$O/fig_pipeline"
run fig_forest.stdout $PY "$A/fig_forest.py" "$O/boot.json" "$O/fig_forest"
run fig_arms.stdout $PY "$A/fig_arms.py" "$O/allsets.json" "$O/fig_arms"

echo "=== sheets and keys rebuilt from the run records vs. the sheets the readers saw"
for k in restr auth; do
  same "$O/dev_${k}_sheet.txt" "$D/ov310/labels/${k}_sheet.txt" "Dev $k sheet"
  same "$O/dev_${k}_key.json" "$D/ov310/labels/${k}_key.json" "Dev $k key"
  same "$O/test_${k}_sheet.txt" "$D/test310/labels/test_${k}_sheet.txt" "Test $k sheet"
  same "$O/test_${k}_key.json" "$D/test310/labels/test_${k}_key.json" "Test $k key"
  for v in s b; do
    same "$O/h3${v}_${k}_sheet.txt" "$D/h3/labels/h3${v}_${k}_sheet.txt" "compaction prompt h3$v $k sheet"
    same "$O/h3${v}_${k}_key.json" "$D/h3/labels/h3${v}_${k}_key.json" "compaction prompt h3$v $k key"
  done
  same "$O/f2_${k}_sheet.txt" "$D/f1f2/labels/f2_${k}_sheet.txt" "F2 $k sheet"
  same "$O/f2_${k}_key.json" "$D/f1f2/labels/f2_${k}_key.json" "F2 $k key"
  same "$O/f3_${k}_sheet.txt" "$D/f3/labels/f3_${k}_sheet.txt" "F3 $k sheet"
  same "$O/f3_${k}_key.json" "$D/f3/labels/f3_${k}_key.json" "F3 $k key"
  same "$O/f3c_${k}_sheet.txt" "$D/f3c/labels/f3c_${k}_sheet.txt" "F3c $k sheet"
  same "$O/f3c_${k}_key.json" "$D/f3c/labels/f3c_${k}_key.json" "F3c $k key"
  same "$O/f4_${k}_sheet.txt" "$D/f4/labels/f4_${k}_sheet.txt" "F4 $k sheet"
  same "$O/f4_${k}_key.json" "$D/f4/labels/f4_${k}_key.json" "F4 $k key"
done
echo "=== replay target files"
for t in f1f2/targets/targets_f2_qwen3_8b.json f1f2/targets/targets_f2_gptoss_20b.json f3/targets/targets_f3_gptoss_120b.json f3c/targets/targets_f3c_qwen3_235b.json f4/targets/targets_f4_qwen3_8b.json f4/targets/targets_f4_gptoss_20b.json; do
  same "$O/$(basename "$t")" "$D/$t" "$(basename "$t")"
done
echo "=== figures"
for f in fig_pipeline fig_forest fig_arms; do
  if [ -s "$O/$f.pdf" ]; then echo "drawn: $f.pdf"; else echo "FAILED: $f.pdf missing"; BAD=1; fi
done
if [ -n "$REF" ]; then
  echo "=== recomputed analyses vs. reference outputs"
  for p in "$REF"/*; do
    f=$(basename "$p")
    if [ -f "$O/$f" ]; then same "$O/$f" "$p" "$f"; else echo "FAILED: $f not produced"; BAD=1; fi
  done
fi
if [ "$BAD" = 0 ]; then echo "ALL MATCH"; exit 0; else echo "SOME STEPS FAILED OR DIFFER"; exit 1; fi
