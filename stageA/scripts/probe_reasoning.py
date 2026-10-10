"""Does the server show the model its earlier reasoning? (harness v0.3 sends it back)

Sends the same short tool-use history twice through the harness's own client, once with the
`reasoning` field on the assistant messages and once without, and compares the prompt token counts
the server reports. This goes through vLLM's real chat path (chat template or harmony conversion),
so it answers the question for the exact server and model. Two checks: a mid-task prompt (with
tools) and the compaction prompt (new user message, no tools). Run by slurm/stageA.sbatch after
the servers are up; it can also be run by hand:

  python scripts/probe_reasoning.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1
"""
import argparse
import json

import _path  # noqa: F401
from sid.agent import DEFAULT_COMPACTION_PROMPT
from sid.runner import model_factory

NOTE = ("The ticket asks for a refund on order ORD-1. Refunds need approval from finance, so before acting I "
        "should read the customer record and then ask for confirmation instead of issuing it directly. ")
TOOLS = [{"type": "function", "function": {
    "name": "read_ticket", "description": "Read a support ticket.",
    "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}}]


def history(with_reasoning: bool) -> list:
    msgs = [{"role": "system", "content": "You are a support agent. Use the tools."},
            {"role": "user", "content": "Please handle ticket T-1."}]
    for i in (1, 2):
        a = {"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{i}", "type": "function",
             "function": {"name": "read_ticket", "arguments": json.dumps({"ticket_id": "T-1"})}}]}
        if with_reasoning:
            a["reasoning"] = NOTE * 3
        msgs += [a, {"role": "tool", "tool_call_id": f"c{i}", "name": "read_ticket",
                     "content": "Ticket T-1: customer C-9 asks for a refund on ORD-1."}]
    return msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="vllm:<served-name>@<url>")
    args = ap.parse_args()
    llm = model_factory(args.model, max_tokens=1)()
    for label, extra, tools in (("mid-task", [], TOOLS),
                                ("compaction", [{"role": "user", "content": DEFAULT_COMPACTION_PROMPT}], None)):
        n = []
        for keep in (True, False):
            r = llm.chat(history(keep) + extra, tools=tools, seed=0, max_tokens=1)
            n.append(int((r.usage or {}).get("prompt_tokens") or 0))
        seen = n[0] - n[1] > 50
        print(f"[probe] {label:10s} prompt tokens with reasoning {n[0]}, without {n[1]}: "
              f"earlier reasoning {'IS' if seen else 'is NOT'} shown to the model")


if __name__ == "__main__":
    main()
