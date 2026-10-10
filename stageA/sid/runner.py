"""Model factory, parallel job runner, JSONL output, run manifest.

Model specs
  mock:<policy>                         scripted mock (tests only)
  vllm:<served-model-name>@<base_url>   any OpenAI-compatible server, e.g.
                                        vllm:Qwen/Qwen3-8B@http://localhost:8000/v1
                                        (comma-separated URLs = round-robin over several servers)
  openai:<name>@<base_url>              the same client and presets, without the vLLM serving checks
  api:<model>@<base_url>                v0.3.10.3: a hosted chat API with tool calling, e.g.
                                        api:gpt-4.1@https://api.openai.com/v1; no presets, the provider's
                                        sampling defaults unless --temperature/--top-p are given
The API key comes from SID_API_KEY. Sampling presets are chosen from the model name and can be overridden.
Runs are resumable: a job whose job_id is already in the output file is skipped.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import hashlib
import json
import os
import platform
import socket
import sys
import threading
import time
import traceback
from typing import Callable, Optional

from . import __version__
from .llm import MockLLM, OpenAIChatLLM

# Sampling presets. These follow the model cards as far as we know them;
# check each card before the confirmatory run and record what you used.
PRESETS = {
    "qwen3": dict(temperature=0.6, top_p=0.95,
                  extra_body={"top_k": 20, "chat_template_kwargs": {"enable_thinking": True}}),
    "gpt-oss": dict(temperature=1.0, top_p=1.0, extra_body={"reasoning_effort": "medium"}),
    "glm": dict(temperature=0.7, top_p=0.95, extra_body={}),
    "default": dict(temperature=0.7, top_p=0.95, extra_body={}),
}


def preset_for(model_name: str) -> dict:
    low = model_name.lower()
    for key in ("qwen3", "gpt-oss", "glm"):
        if key in low:
            return json.loads(json.dumps(PRESETS[key]))
    return json.loads(json.dumps(PRESETS["default"]))


def model_factory(spec: str, temperature: Optional[float] = None, top_p: Optional[float] = None,
                  max_tokens: int = 4096, thinking: Optional[bool] = None,
                  extra_body: Optional[dict] = None) -> Callable[[], object]:
    """Return a zero-argument callable that builds a fresh client (one per job/thread)."""
    if spec.startswith("mock:"):
        policy = spec.split(":", 1)[1]
        if policy == "keyword-monitor":
            from .monitor import KeywordMonitor
            return KeywordMonitor
        if policy == "rule-judge":
            from .label.judge import RuleJudge
            return RuleJudge
        return lambda: MockLLM(policy)
    if spec.startswith("vllm:") or spec.startswith("openai:") or spec.startswith("api:"):
        body = spec.split(":", 1)[1]
        name, _, url = body.partition("@")
        url = url or os.environ.get("SID_BASE_URL", "http://localhost:8000/v1")
        urls = [u.strip() for u in url.split(",") if u.strip()]   # several servers: round-robin
        rr = {"i": 0}
        lock = threading.Lock()

        def next_url():
            with lock:
                u = urls[rr["i"] % len(urls)]
                rr["i"] += 1
            return u
        api = spec.startswith("api:")
        # v0.3.10.3: no model-card preset for a hosted API (vLLM-only fields such as top_k would be refused)
        p = dict(temperature=None, top_p=None, extra_body={}) if api else preset_for(name)
        if temperature is not None:
            p["temperature"] = temperature
        if top_p is not None:
            p["top_p"] = top_p
        eb = p["extra_body"]
        if thinking is not None and "qwen3" in name.lower() and not api:
            eb.setdefault("chat_template_kwargs", {})["enable_thinking"] = thinking
        if extra_body:
            eb.update(extra_body)
        api_key = os.environ.get("SID_API_KEY", "EMPTY")
        return lambda: OpenAIChatLLM(next_url(), name, api_key=api_key, temperature=p["temperature"],
                                     top_p=p["top_p"], max_tokens=max_tokens, extra_body=eb,
                                     api_style="api" if api else "vllm")
    raise ValueError(f"unknown model spec: {spec}")


def describe_model(spec: str, **kw) -> dict:
    if spec.startswith("mock:"):
        return {"spec": spec}
    name = spec.split(":", 1)[1].partition("@")[0]
    p = dict(temperature="provider default", top_p="provider default", extra_body={}) if spec.startswith("api:") \
        else preset_for(name)
    p.update({k: v for k, v in kw.items() if v is not None})
    return {"spec": spec, **p}


# ---------------------------------------------------------------- output
class JsonlWriter:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.lock = threading.Lock()

    def write(self, obj: dict):
        line = json.dumps(obj, default=str)
        with self.lock, open(self.path, "a") as f:
            f.write(line + "\n")


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass          # a half-written last line after a crash
    return out


def done_ids(path: str, key: str = "job_id") -> set:
    return {r.get(key) for r in read_jsonl(path) if r.get(key) and not r.get("error")}


def last_attempt(rows: list[dict]) -> list[dict]:
    """v0.3.9: the rows of each job's last execution. run_jobs stamps every row of one execution of a job with
    the same "attempt"; a resumed run re-runs a job that has no good row, and its old rows must not be counted
    twice. Files written before v0.3.9 have no stamp: there, a job-level error row is dropped when the same job
    has good rows."""
    last = {}
    for r in rows:
        last[r.get("job_id")] = r.get("attempt")
    keep = [r for r in rows if r.get("attempt") == last.get(r.get("job_id"))]
    good_jobs = {r.get("job_id") for r in keep if not r.get("error")}
    keep = [r for r in keep if not (r.get("error") and not r.get("run_error") and r.get("job_id") in good_jobs)]
    # unstamped job that failed more than once: one job-level error row, the last
    last_err = {}
    for i, r in enumerate(keep):
        if r.get("error") and not r.get("run_error") and r.get("attempt") is None:
            last_err[r.get("job_id")] = i
    return [r for i, r in enumerate(keep) if not (r.get("error") and not r.get("run_error") and r.get("attempt") is None
                                                   and last_err.get(r.get("job_id")) != i)]


def run_jobs(jobs: list[dict], fn: Callable[[dict], object], out_path: str, workers: int = 8,
             label: str = "jobs") -> dict:
    """Run fn(job) for each job in a thread pool. fn returns a dict or a list of dicts;
    every row gets the job_id. Errors are logged as rows with an 'error' field."""
    w = JsonlWriter(out_path)
    skip = done_ids(out_path)
    todo = [j for j in jobs if j["job_id"] not in skip]
    t0, n_ok, n_err = time.time(), 0, 0
    run_err = [0]                  # v0.3.9: single failed runs inside finished jobs (sid.replay.run_arms)
    print(f"[{label}] {len(todo)} to run, {len(jobs) - len(todo)} already done -> {out_path}",
          flush=True)

    def wrap(job):
        att = f"{time.time():.6f}-{os.getpid()}-{threading.get_ident()}"     # v0.3.9: see last_attempt
        try:
            res = fn(job)
            rows = res if isinstance(res, list) else [res]
            n_run_err = 0
            for r in rows:
                r.setdefault("job_id", job["job_id"])
                r.setdefault("attempt", att)
                n_run_err += bool(r.get("run_error"))
                w.write(r)
            run_err[0] += n_run_err
            return True
        except Exception as e:
            w.write({"job_id": job["job_id"], "error": repr(e), "traceback": traceback.format_exc(), "attempt": att})
            return False

    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(wrap, j) for j in todo]
        for i, f in enumerate(cf.as_completed(futs), 1):
            if f.result():
                n_ok += 1
            else:
                n_err += 1
            if i % max(1, len(todo) // 20) == 0 or i == len(todo):
                el = time.time() - t0
                extra = f", {run_err[0]} failed single runs" if run_err[0] else ""
                print(f"[{label}] {i}/{len(todo)} done, {n_err} errors{extra}, {el / 60:.1f} min", flush=True)
    return {"ran": len(todo), "ok": n_ok, "errors": n_err, "run_errors": run_err[0], "seconds": time.time() - t0}


# ---------------------------------------------------------------- manifest
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# v0.3.8: everything that defines an experiment, not only sid/*.py (keys are paths from the repo root)
CODE_GLOBS = ("sid/**/*.py", "scripts/*.py", "slurm/*", "tests/**/*.py", "PROTOCOL.md", "docs/FROZEN_TEST_SET.json")


def source_hashes() -> dict:
    out = {}
    for pat in CODE_GLOBS:
        for p in sorted(glob.glob(os.path.join(REPO, pat), recursive=True)):
            if os.path.isfile(p) and "__pycache__" not in p:
                with open(p, "rb") as f:
                    out[os.path.relpath(p, REPO)] = hashlib.sha256(f.read()).hexdigest()
    return out


def code_identity() -> dict:
    """One digest over all experiment files, the release archive's SHA-256 if ARCHIVE_SHA256.txt was written
    at deployment (`sha256sum stageA_vX.zip > ~/stageA/ARCHIVE_SHA256.txt`), and the git commit if any."""
    hashes = source_hashes()
    tree = hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(hashes.items())).encode()).hexdigest()
    arch = None
    ap = os.path.join(REPO, "ARCHIVE_SHA256.txt")
    if os.path.isfile(ap):
        with open(ap) as f:
            arch = f.read().strip() or None
    commit = None
    # v0.3.10.3: also a git repository one level up (stageA/ inside a clone of the whole package)
    if any(os.path.isdir(os.path.join(d, ".git")) for d in (REPO, os.path.dirname(REPO))):
        try:
            import subprocess
            commit = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True,
                                    timeout=10).stdout.strip() or None
        except Exception:  # noqa: BLE001
            commit = None
    return {"code_tree_sha256": tree, "archive_sha256": arch, "git_commit": commit,
            "frozen_test_set_sha256": hashes.get("docs/FROZEN_TEST_SET.json")}


def _pkg_version(name: str) -> Optional[str]:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:  # noqa: BLE001
        return None


def model_fingerprint(model_dir: Optional[str]) -> dict:
    """What identifies the served weights (v0.3.7): file names and sizes, SHA-256 of the small config and
    tokenizer files, and the Hugging Face commit recorded by the downloader (.cache/huggingface/download/
    *.metadata, first line). Hashing the weight shards themselves would take minutes, so they are listed by
    size only. Never raises."""
    out: dict = {"model_dir": model_dir}
    try:
        if not model_dir or not os.path.isdir(model_dir):
            out["error"] = "no model directory"
            return out
        files, small = {}, {}
        for name in sorted(os.listdir(model_dir)):
            fp = os.path.join(model_dir, name)
            if os.path.isfile(fp):
                files[name] = os.path.getsize(fp)
                if files[name] < 5_000_000 and name.endswith((".json", ".jinja", ".txt", ".model", ".py")):
                    with open(fp, "rb") as f:
                        small[name] = hashlib.sha256(f.read()).hexdigest()
        commits = set()
        meta_dir = os.path.join(model_dir, ".cache", "huggingface", "download")
        if os.path.isdir(meta_dir):
            for root, _dirs, names in os.walk(meta_dir):
                for name in names:
                    if name.endswith(".metadata"):
                        with open(os.path.join(root, name)) as f:
                            first = f.readline().strip()
                        if first:
                            commits.add(first)
        rev = None
        for name in ("REVISION", ".revision"):
            rp = os.path.join(model_dir, name)
            if os.path.isfile(rp):
                with open(rp) as f:
                    rev = f.readline().strip() or None
                break
        out.update({"files": files, "sha256_small_files": small, "hf_commits": sorted(commits),
                    "revision_file": rev})
    except Exception as e:  # noqa: BLE001 - a manifest must never stop a run
        out["error"] = repr(e)
    return out


def served_models(spec: Optional[str]) -> list:
    """GET <url>/models for each URL of a vllm spec (id, root path, max_model_len). Never raises."""
    if not spec or not str(spec).startswith("vllm:") or "@" not in spec:
        return []
    import urllib.request
    out = []
    for url in spec.split("@", 1)[1].split(","):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url.rstrip("/") + "/models", timeout=5) as r:
                data = json.loads(r.read().decode())
            out.append({"url": url, "models": [{k: m.get(k) for k in ("id", "root", "max_model_len", "owned_by")}
                                               for m in data.get("data", [])]})
        except Exception as e:  # noqa: BLE001
            out.append({"url": url, "error": repr(e)})
    return out


def write_manifest(out_dir: str, args: argparse.Namespace, extra: Optional[dict] = None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    try:
        import openai
        oa = openai.__version__
    except Exception:
        oa = None
    man = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "argv": sys.argv, "args": vars(args),
           "sid_version": __version__, "python": sys.version, "platform": platform.platform(),
           "host": socket.gethostname(), "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
           "openai_version": oa, "source_sha256": source_hashes(), "code": code_identity(),
           # v0.3.7: which weights and server produced the run
           "serving": {"env": {k: os.environ.get(k) for k in ("MODEL_DIR", "SERVED_NAME", "TP", "MAXLEN", "PARSER_ARGS",
                                                               "EXTRA_SERVE_ARGS", "SIF", "VENV", "WORKERS")},
                       "vllm_version": _pkg_version("vllm"),
                       "model": model_fingerprint(os.environ.get("MODEL_DIR")),
                       "served": served_models(getattr(args, "model", None)) +
                                 (served_models(getattr(args, "successor", None))
                                  if getattr(args, "successor", None) else [])},
           **(extra or {})}
    path = os.path.join(out_dir, f"manifest_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w") as f:
        json.dump(man, f, indent=1, default=str)
    problems = serving_problems(man, args)
    if problems:
        raise SystemExit("refusing a test-split run without a complete record of what produced it "
                         f"(manifest {path}): " + "; ".join(problems))
    return path


def serving_problems(man: dict, args) -> list:
    """v0.3.8 fail-fast for the confirmatory (test split) runs on a served model: the weights, the server and
    the code must be identifiable. Dev runs and mock models only record what is there."""
    specs = [getattr(args, "model", None), getattr(args, "successor", None)]
    if getattr(args, "split", "dev") != "test" or not any(str(x or "").startswith("vllm:") for x in specs):
        return []
    sv, out = man.get("serving", {}), []
    model = sv.get("model", {})
    if model.get("error"):
        out.append(f"model directory: {model['error']} (MODEL_DIR={model.get('model_dir')})")
    if not model.get("sha256_small_files", {}).get("config.json"):
        out.append("no config.json hash")
    if not (model.get("hf_commits") or model.get("revision_file")):
        out.append("no Hugging Face commit (.cache/huggingface/download/*.metadata) and no REVISION file in "
                   "MODEL_DIR; write the commit into MODEL_DIR/REVISION")
    if not sv.get("served") or any("error" in x for x in sv["served"]):
        out.append("the vLLM /models query failed")
    if not (man.get("code", {}).get("archive_sha256") or man.get("code", {}).get("git_commit")):
        out.append("no ARCHIVE_SHA256.txt and no git commit in the repo")
    return out


# ---------------------------------------------------------------- shared CLI
def common_args(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--model", required=True,
                   help="writer model spec (mock:<policy> | vllm:<name>@<url> | openai:<name>@<url> | api:<model>@<url>)")
    p.add_argument("--successor", default=None, help="successor model spec (default: same as --model)")
    p.add_argument("--split", default="dev", choices=["dev", "test"])
    p.add_argument("--families", nargs="*", default=None)
    p.add_argument("--templates", nargs="*", default=None, help="template id suffixes, e.g. R1_dedupe_pending")
    p.add_argument("--seeds", type=int, default=5, help="instances (surface seeds) per template")
    p.add_argument("--seed-offset", type=int, default=0)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-p", type=float, default=None)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--summary-max-tokens", type=int, default=4096,
                   help="token cap for the compaction call, reasoning included (H3a factor)")
    p.add_argument("--thinking", choices=["on", "off"], default=None, help="Qwen3 thinking switch")
    p.add_argument("--enforce", action="store_true", help="tool-side permission guard (mitigation arm)")
    p.add_argument("--compaction-prompt", default="neutral", choices=["neutral", "structured", "brief"],
                   help="compaction prompt wording (H3b factor)")
    p.add_argument("--no-keep-reasoning", action="store_true",
                   help="do not send earlier reasoning back to the model (v0.2 behavior; ablation)")
    p.add_argument("--system-prompt", default="default", choices=["default", "scoped"],
                   help="v0.3.10.2: system-prompt variant (default = the prompt of all earlier runs)")
    p.add_argument("--fixed-step-only", action="store_true",
                   help="compact only at the template step, never just before the agent ends (v0.2 rule)")
    return p


HARNESS = "v0.3.4"   # bump when a change alters trajectories; it goes into every job id (v0.3.4: tools.py fix)


def spec_id(spec) -> str:
    """Model spec without server URLs ("vllm:Qwen/Qwen3-8B@http://...:23312/v1" -> "vllm:Qwen/Qwen3-8B").
    The port depends on the Slurm job id, so URLs must not be part of a job id or a model comparison:
    otherwise a resumed run in a new Slurm job would redo every finished job."""
    return str(spec or "").split("@", 1)[0]


def settings_tag(args) -> str:
    """Every CLI setting that changes trajectories goes into job ids, so a re-run with a
    different setting into the same folder is not skipped as 'already done'."""
    keys = ("compaction_prompt", "summary_max_tokens", "max_tokens", "thinking", "temperature", "top_p",
            "enforce", "no_keep_reasoning", "fixed_step_only")
    tag = ",".join([f"harness={HARNESS}"] + [f"{k}={getattr(args, k, None)}" for k in keys])
    # v0.3.10.2: only a non-default system prompt enters the id, so default runs keep their v0.3.10.1 ids
    if getattr(args, "system_prompt", "default") != "default":
        tag += f",system_prompt={args.system_prompt}"
    return tag


def verify_frozen_test_split():
    """Refuse to run on the test split if it differs from docs/FROZEN_TEST_SET.json."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "docs", "FROZEN_TEST_SET.json")
    if not os.path.exists(path):
        raise SystemExit("test split is not frozen yet (scripts/freeze_test_set.py --write)")
    sys.path.insert(0, os.path.join(root, "scripts"))
    from freeze_test_set import current
    frozen = json.load(open(path))
    inst, _ = current()
    if inst != frozen["instances"]:
        raise SystemExit("test split changed since it was frozen; see DEVIATIONS.md / freeze_test_set.py --verify")


def factory_from_args(args, spec: Optional[str] = None):
    if getattr(args, "split", None) == "test":
        verify_frozen_test_split()
    th = None if args.thinking is None else args.thinking == "on"
    return model_factory(spec or args.model, temperature=args.temperature, top_p=args.top_p,
                         max_tokens=args.max_tokens, thinking=th)
