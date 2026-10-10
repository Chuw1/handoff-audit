"""Checks the real OpenAI-compatible client path against a tiny fake server
(no GPU, no network). Covers native tool calls, text-fallback tool calls,
reasoning_content, and a full episode through the `vllm:` model spec."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sid.agent import run_episode  # noqa: E402
from sid.runner import model_factory  # noqa: E402
from sid.tasks import get_instance  # noqa: E402

SEEN = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        msgs, tools = body["messages"], body.get("tools")
        n_tool = sum(1 for m in msgs if m["role"] == "tool")
        msg = {"role": "assistant", "content": None, "reasoning_content": "thinking about the task"}
        finish = "tool_calls"
        if not tools:
            msg["content"] = "Summary: I listed the records. Deletion needs approval, which is pending."
            finish = "stop"
        elif n_tool < 3:
            msg["tool_calls"] = [{"id": f"c{n_tool}", "type": "function",
                                  "function": {"name": "list_records", "arguments": "{}"}}]
        elif n_tool == 3:
            # model writes the call as text (tests the fallback parser)
            msg["content"] = '<tool_call>{"name": "list_records", "arguments": {}}</tool_call>'
            finish = "stop"
        else:
            msg["tool_calls"] = [{"id": "cf", "type": "function",
                                  "function": {"name": "finish",
                                               "arguments": json.dumps({"answer": "Approval pending."})}}]
        out = {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
               "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
               "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_episode_through_openai_client():
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}/v1"
        make = model_factory(f"vllm:Qwen/Qwen3-8B@{url}", max_tokens=256)
        task = get_instance("dev:R1_dedupe_pending", 0)
        task.compaction_after_step = 2
        tr = run_episode(task, make(), seed=5)
        assert tr["compacted"]
        assert tr["summary"]["reasoning"] == "thinking about the task"
        assert "pending" in tr["summary"]["text"]
        post_turns = tr["post"]["turns"]
        assert any(t["parse_fallback"] for t in post_turns)
        assert tr["post"]["finished"] and not tr["violations_post"]
        # Qwen3 preset: thinking switch and top_k reach the server via extra_body
        b = SEEN[0]
        assert b["chat_template_kwargs"]["enable_thinking"] is True and b["top_k"] == 20
        assert b["temperature"] == 0.6 and "seed" in b
        # the compaction call has no tools and the summary hand-off drops the original request
        comp = [x for x in SEEN if not x.get("tools")]
        assert comp and "[COMPACTION]" in comp[0]["messages"][-1]["content"]
        post_first = SEEN[len(tr["turns_pre"]) + 1]
        roles = [m["role"] for m in post_first["messages"]]
        assert roles == ["system", "user"] and "Summary of earlier work" in post_first["messages"][1]["content"]
    finally:
        srv.shutdown()
