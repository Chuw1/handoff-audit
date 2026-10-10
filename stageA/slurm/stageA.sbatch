#!/bin/bash -l
# Start vLLM server(s) on one node, wait until healthy, run one Stage A script
# against them, then shut the servers down. Runs inside the vLLM Apptainer image
# ($SIF) if it exists, otherwise from a Python venv with vllm ($VENV, made by
# slurm/setup_venv.sh). The client only needs python3 + openai, which both have.
#
# Usage (from the repo root):
#   mkdir -p logs
#   sbatch --export=ALL,MODEL_DIR=$HOME/models/Qwen3-8B,SERVED_NAME=Qwen/Qwen3-8B,\
#   STAGE="scripts/run_capability_screen.py --n 30 --out runs/screen_qwen3_8b" slurm/stageA.sbatch
#
# CHECK BEFORE FIRST USE
#   * set --account and --partition below for your cluster (`sinfo -s`)
#   * parser names were checked against the vllm 0.30.0 source (tool: hermes, openai; reasoning: qwen3,
#     openai_gptoss); re-check if you change the vLLM version
#   * the scripts resume (finished job_ids are skipped) and this job requeues itself, so it can run
#     on a preemptible queue
#
#SBATCH --job-name=sidA
#SBATCH --account=PROJECT_ACCOUNT
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --gpus-per-node=2
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --open-mode=append
#SBATCH --requeue

set -eo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
mkdir -p logs

MODEL_DIR=${MODEL_DIR:-$HOME/models/Qwen3-8B}
SERVED_NAME=${SERVED_NAME:-Qwen/Qwen3-8B}
SIF=${SIF:-$HOME/vllm.sif}        # Apptainer image (preferred if it exists)
VENV=${VENV:-$HOME/venvs/vllm}    # or a Python venv with vllm (slurm/setup_venv.sh)
TP=${TP:-1}                       # tensor parallel per server; servers = GPUs / TP
MAXLEN=${MAXLEN:-32768}
WORKERS=${WORKERS:-32}            # concurrent episodes (client threads)
STAGE=${STAGE:?set STAGE, e.g. "scripts/run_discovery.py --seeds 5 --samples 4 --out runs/disc_x"}
STAGE2=${STAGE2:-}                # optional further scripts, run on the same servers after STAGE
STAGE3=${STAGE3:-}
STAGE4=${STAGE4:-}                # v0.3.10: up to six stages per job
STAGE5=${STAGE5:-}
STAGE6=${STAGE6:-}
PRECHECK=${PRECHECK:-}            # optional python script + args; if it exits non-zero, the job stops
                                  # before starting vLLM (e.g. scripts/check_screen.py <screen dir>)
EXTRA_SERVE_ARGS=${EXTRA_SERVE_ARGS:-}

case "$SERVED_NAME" in
  *[Qq]wen3*)  PARSER_ARGS=${PARSER_ARGS:-"--enable-auto-tool-choice --tool-call-parser hermes --reasoning-parser qwen3"} ;;
  *gpt-oss*)   PARSER_ARGS=${PARSER_ARGS:-"--enable-auto-tool-choice --tool-call-parser openai --reasoning-parser openai_gptoss"} ;;  # checked in vllm 0.30.0
  *GLM*|*glm*) PARSER_ARGS=${PARSER_ARGS:-"--enable-auto-tool-choice --tool-call-parser glm45 --reasoning-parser glm45"} ;;      # names exist in vllm 0.30.0 (glm47 too)
  *)           PARSER_ARGS=${PARSER_ARGS:-"--enable-auto-tool-choice --tool-call-parser hermes"} ;;
esac

export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
export HF_HUB_OFFLINE=1 HF_HOME=${HF_HOME:-$HOME/hf}

IFS=',' read -r -a ALLGPU <<< "${CUDA_VISIBLE_DEVICES:-0,1}"
NGPU=${#ALLGPU[@]}
NSERV=$(( NGPU / TP ))
echo "node=$(hostname) gpus=${CUDA_VISIBLE_DEVICES:-?} servers=$NSERV tp=$TP model=$MODEL_DIR"
if [ -f "$SIF" ]; then
  # apptainer is a module on our cluster (not on the default PATH)
  command -v apptainer >/dev/null || module load apptainer
  command -v apptainer >/dev/null || { echo "apptainer not found"; exit 1; }
  vllm_cmd() { apptainer exec --nv "$SIF" vllm "$@"; }
  py_cmd()   { apptainer exec --nv "$SIF" python3 "$@"; }
  echo "runtime: apptainer $SIF"
elif [ -x "$VENV/bin/vllm" ]; then
  vllm_cmd() { "$VENV/bin/vllm" "$@"; }
  py_cmd()   { "$VENV/bin/python" "$@"; }
  echo "runtime: venv $VENV"
else
  echo "no runtime: neither $SIF nor $VENV/bin/vllm exists (see slurm/setup_venv.sh)"; exit 1
fi
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv || true
py_cmd -c "import sys, vllm, openai, torch; print('vllm', vllm.__version__, 'openai', openai.__version__, 'torch', torch.__version__, 'cuda', torch.version.cuda, 'gpu_ok', torch.cuda.is_available()); sys.exit(0 if torch.cuda.is_available() else 3)" \
  || { echo "STOP: this runtime cannot use the GPU (driver/CUDA build mismatch?). See slurm/setup_venv.sh"; exit 1; }

if [ -n "$PRECHECK" ]; then
  if ! py_cmd $PRECHECK; then echo "SKIP: precheck did not pass ($PRECHECK); nothing else runs"; exit 0; fi
fi

# job-specific ports, so two jobs on one node never talk to each other's servers
PORT0=$(( 20000 + ( ${SLURM_JOB_ID:-$$} % 2000 ) * 16 ))
PIDS=(); URLS=""
for (( i=0; i<NSERV; i++ )); do
  PORT=$(( PORT0 + i ))
  GPUS=$(IFS=','; echo "${ALLGPU[*]:$(( i*TP )):$TP}")
  CUDA_VISIBLE_DEVICES=$GPUS vllm_cmd serve "$MODEL_DIR" \
      --served-model-name "$SERVED_NAME" --port $PORT --tensor-parallel-size $TP \
      --max-model-len $MAXLEN --gpu-memory-utilization 0.90 --seed 0 $PARSER_ARGS $EXTRA_SERVE_ARGS \
      > "logs/vllm_${SLURM_JOB_ID:-local}_$i.log" 2>&1 &
  PIDS+=($!)
  URLS="${URLS:+$URLS,}http://localhost:$PORT/v1"
done
trap 'kill ${PIDS[@]} 2>/dev/null || true' EXIT

for (( i=0; i<NSERV; i++ )); do
  PORT=$(( PORT0 + i )); t=0
  # ready = our own process is alive AND the port serves our model name
  until curl -sf "http://localhost:$PORT/v1/models" 2>/dev/null | grep -q "\"$SERVED_NAME\""; do
    if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
      echo "server $i exited"; tail -50 "logs/vllm_${SLURM_JOB_ID:-local}_$i.log"; exit 1
    fi
    sleep 10; t=$(( t + 10 ))
    if (( t > 1500 )); then echo "server $i did not come up"; tail -50 "logs/vllm_${SLURM_JOB_ID:-local}_$i.log"; exit 1; fi
  done
  echo "server $i ready on port $PORT after ${t}s"
done

# what the model sees of its earlier reasoning on this server (v0.3); never fatal
py_cmd scripts/probe_reasoning.py --model "vllm:$SERVED_NAME@${URLS%%,*}" || echo "[probe] failed (not fatal)"

# the run manifests record these (v0.3.7: which weights, server and parsers produced the run)
export MODEL_DIR SERVED_NAME TP MAXLEN PARSER_ARGS EXTRA_SERVE_ARGS SIF VENV WORKERS
# v0.3.10: a failed stage no longer skips the stages after it; the job still exits non-zero at the end
NFAIL=0
for st in "$STAGE" "$STAGE2" "$STAGE3" "$STAGE4" "$STAGE5" "$STAGE6"; do
  [ -z "$st" ] && continue
  echo "=== stage: $st"
  if py_cmd $st --model "vllm:$SERVED_NAME@$URLS" --workers $WORKERS; then
    echo "done: $st"
  else
    echo "FAILED (exit $?): $st"; NFAIL=$(( NFAIL + 1 ))
  fi
done
[ "$NFAIL" -eq 0 ] || { echo "$NFAIL stage(s) failed"; exit 1; }
