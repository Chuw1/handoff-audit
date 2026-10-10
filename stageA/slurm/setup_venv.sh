#!/bin/bash
# Alternative to the Apptainer image: a Python 3.12 venv with vLLM in $HOME/venvs/vllm.
# Run on the LOGIN node (it has internet). Takes ~10-20 minutes.
#   rm -rf ~/venvs/vllm            # only if an older venv exists
#   bash slurm/setup_venv.sh 2>&1 | tee logs/setup_venv.log
#
# Which CUDA build: the login node reports an old driver (CUDA 12.6, "found version 12060"), but the
# GPU nodes run driver 580.126.09 (CUDA 13.0; measured on 2026-10-01). This script
# installs vLLM's official CUDA 12.9 build (+cu129) with PyTorch cu129, which was verified on a GPU node
# (slurm/gpu_check.sbatch: gpu_ok True, matmul ok, vllm CLI ok). CU=130 (the PyPI default) also works
# on those nodes.
# Note: `vllm serve --help` cannot run on the login node (no GPU: "Failed to infer device type");
# that is expected and is not checked here.
set -eo pipefail
VENV=${VENV:-$HOME/venvs/vllm}
VLLM_VERSION=${VLLM_VERSION:-0.30.0}
CU=${CU:-129}
export UV_LINK_MODE=copy UV_CACHE_DIR=${UV_CACHE_DIR:-$HOME/.cache/uv}
if [ -x "$VENV/bin/vllm" ]; then echo "$VENV already has vllm; remove it first (rm -rf $VENV)"; exit 1; fi
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  python3 -m pip install --user -U uv
fi
UV=$(command -v uv || echo "$HOME/.local/bin/uv")
"$UV" --version
"$UV" python install 3.12
[ -x "$VENV/bin/python" ] || "$UV" venv --python 3.12 "$VENV"     # reuse an empty venv from a failed run
install() { VIRTUAL_ENV="$VENV" "$UV" pip install "$@"; }
if [ "$CU" = "130" ]; then
  install "vllm==$VLLM_VERSION" openai
else
  WHEEL="https://github.com/vllm-project/vllm/releases/download/v${VLLM_VERSION}/vllm-${VLLM_VERSION}+cu${CU}-cp38-abi3-manylinux_2_28_x86_64.whl"
  # --torch-backend takes only PyTorch's own packages from the PyTorch index and everything else from
  # PyPI. (A plain --extra-index-url fails: that index also hosts an old `packaging`, and uv by default
  # takes each package from the first index that has it.) Fallback for uv versions without it:
  install "$WHEEL" openai --torch-backend="cu${CU}" || \
    install "$WHEEL" openai --extra-index-url "https://download.pytorch.org/whl/cu${CU}" --index-strategy unsafe-best-match
fi
WANT="${CU:0:2}.${CU:2}"
"$VENV/bin/python" - "$WANT" <<'PY'
import sys, torch, vllm, openai
print("vllm", vllm.__version__, "| openai", openai.__version__, "| torch", torch.__version__, "| built for CUDA", torch.version.cuda)
if torch.version.cuda != sys.argv[1]:
    sys.exit(f"ERROR: torch is built for CUDA {torch.version.cuda}, expected {sys.argv[1]}")
PY
echo "venv ready: $VENV (GPU use is checked on a GPU node: sbatch slurm/gpu_check.sbatch)"
