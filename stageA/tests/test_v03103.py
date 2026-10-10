"""v0.3.10.3: the `api:` model spec for hosted chat APIs, against a strict fake server (no network).
The fake refuses what hosted APIs often refuse: `max_tokens` (wants `max_completion_tokens`), `seed`,
temperature together with top_p, fields that are not plain chat-completions fields, and an empty assistant
text next to tool calls. The client may drop or rename only what the harness adds by itself (seed,
tool_choice, the token-cap name); a refused temperature or top_p, which only the user sets, is an error.
The `vllm:` path must send exactly what it sent before."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sid import llm  # noqa: E402
from sid.agent import run_episode  # noqa: E402
from sid.runner import model_factory  # noqa: E402
from sid.tasks import get_instance  # noqa: E402

PLAIN = {"system": {"role", "content"}, "user": {"role", "content"},
         "assistant": {"role", "content", "tool_calls"}, "tool": {"role", "content", "tool_call_id"}}


def _server(strict: bool, refuse_mct: bool = False):
    seen, refused = [], []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _refuse(self, msg, param=None):
            refused.append(msg)
            self._send(400, {"error": {"message": msg, "type": "invalid_request_error", "param": param,
                                       "code": "unsupported_parameter"}})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            if refuse_mct and "max_completion_tokens" in body:
                return self._refuse("Unrecognized request argument supplied: max_completion_tokens")
            if strict:
                if "max_tokens" in body:
                    return self._refuse("Unsupported parameter: 'max_tokens' is not supported with this model. "
                                        "Use 'max_completion_tokens' instead.", "max_tokens")
                if "seed" in body:
                    return self._refuse("Unsupported parameter: 'seed'.", "seed")
                if "temperature" in body and "top_p" in body:
                    return self._refuse("`temperature` and `top_p` cannot both be specified for this model.")
                for m in body["messages"]:
                    extra = set(m) - PLAIN[m["role"]]
                    if extra:
                        return self._send(400, {"error": {"message": f"messages: unexpected fields {sorted(extra)}",
                                                          "param": "messages"}})
                    if m["role"] == "assistant" and m.get("tool_calls") and m.get("content") == "":
                        return self._send(400, {"error": {"message": "text content blocks must be non-empty",
                                                          "param": "messages"}})
            msgs, tools = body["messages"], body.get("tools")
            n_tool = sum(1 for m in msgs if m["role"] == "tool")
            msg = {"role": "assistant", "content": "", "reasoning_content": "private thoughts"}
            finish = "tool_calls"
            if not tools:
                msg["content"] = "Summary: I listed the records. Deletion needs approval, which is pending."
                finish = "stop"
            elif n_tool < 3:
                msg["tool_calls"] = [{"id": f"c{n_tool}", "type": "function",
                                      "function": {"name": "list_records", "arguments": "{}"}}]
            else:
                msg["tool_calls"] = [{"id": "cf", "type": "function",
                                      "function": {"name": "finish", "arguments": json.dumps({"answer": "Pending."})}}]
            self._send(200, {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                             "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                             "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/v1", seen, refused


def _episode(spec, **kw):
    task = get_instance("dev:R1_dedupe_pending", 0)
    task.compaction_after_step = 2
    return run_episode(task, model_factory(spec, max_tokens=256, **kw)(), seed=5)


def test_api_spec_runs_an_episode_against_a_strict_server():
    llm._API_LEARNED.clear()
    srv, url, seen, refused = _server(strict=True)
    try:
        tr = _episode(f"api:strict-model@{url}", temperature=0.5)
        assert tr["compacted"] and "pending" in tr["summary"]["text"] and tr["post"]["finished"]
        # one refusal: seed (dropped); max_completion_tokens is sent from the start, temperature as given
        assert len(refused) == 1, refused
        ok = seen[len(refused):]
        assert ok and all("max_completion_tokens" in b and "max_tokens" not in b and "seed" not in b
                          and "top_p" not in b and b["temperature"] == 0.5 for b in ok)
        # earlier reasoning is kept in the record but not sent back; tool results carry no "name"
        assert tr["summary"]["reasoning"] == "private thoughts"
        assert all(set(m) <= PLAIN[m["role"]] for b in ok for m in b["messages"])
        # a second client of the same endpoint starts from what the first one learned: no new refusals
        _episode(f"api:strict-model@{url}", temperature=0.5)
        assert len(refused) == 1
    finally:
        srv.shutdown()
        llm._API_LEARNED.clear()


def test_api_spec_does_not_drop_sampling_values_the_user_set():
    import openai
    llm._API_LEARNED.clear()
    srv, url, seen, refused = _server(strict=True)
    try:
        try:
            _episode(f"api:strict-model@{url}", temperature=0.5, top_p=0.9)
            raise AssertionError("a refused temperature/top_p pair must fail the episode")
        except openai.BadRequestError as e:
            assert "cannot both be specified" in str(e)
        assert "top_p" not in llm._API_LEARNED[(url, "strict-model")][0]
    finally:
        srv.shutdown()
        llm._API_LEARNED.clear()


def test_api_spec_leaves_sampling_to_the_provider_and_has_no_preset():
    llm._API_LEARNED.clear()
    srv, url, seen, refused = _server(strict=False)
    try:
        _episode(f"api:Qwen/Qwen3-8B@{url}", thinking=True)
        b = seen[0]
        assert "temperature" not in b and "top_p" not in b and "top_k" not in b
        assert "chat_template_kwargs" not in b and "max_tokens" not in b and b["max_completion_tokens"] == 256
        assert "seed" in b and not refused
    finally:
        srv.shutdown()
        llm._API_LEARNED.clear()


def test_api_spec_falls_back_to_max_tokens():
    llm._API_LEARNED.clear()
    srv, url, seen, refused = _server(strict=False, refuse_mct=True)
    try:
        tr = _episode(f"api:old-server@{url}")
        assert tr["compacted"] and len(refused) == 1
        assert all("max_tokens" in b and "max_completion_tokens" not in b for b in seen[1:])
        assert seen[1]["max_tokens"] == 256
    finally:
        srv.shutdown()
        llm._API_LEARNED.clear()


def test_vllm_spec_request_is_unchanged():
    srv, url, seen, refused = _server(strict=False)
    try:
        _episode(f"vllm:Qwen/Qwen3-8B@{url}")
        b = seen[0]
        assert b["temperature"] == 0.6 and b["top_p"] == 0.95 and b["max_tokens"] == 256 and "seed" in b
        assert b["top_k"] == 20 and b["chat_template_kwargs"] == {"enable_thinking": True}
        assert "max_completion_tokens" not in b
        later = [m for x in seen[1:] for m in x["messages"]]
        assert any("reasoning" in m for m in later)                  # interleaved reasoning still sent back
        assert any(m["role"] == "tool" and "name" in m for m in later)
    finally:
        srv.shutdown()


def test_a_refusal_of_anything_else_still_fails():
    import openai

    class E(openai.BadRequestError):
        def __init__(self):
            pass

        def __str__(self):
            return "messages: bad role"
    e = E()
    e.body = {"error": {"message": "messages: bad role", "param": "messages"}}
    assert llm._rejected_param(e, {"messages": [], "seed": 1}) is None
    e.body = {"error": {"message": "Unsupported parameter: 'seed'", "param": "seed", "code": "unsupported_parameter"}}
    assert llm._rejected_param(e, {"messages": [], "seed": 1}) == "seed"
    assert llm._rejected_param(e, {"messages": []}) is None        # not sent: nothing to drop

    class V(E):
        def __str__(self):
            return "max_completion_tokens: integer above maximum value (16384)"
    v = V()
    v.body = {"error": {"message": str(v), "param": "max_completion_tokens", "code": "integer_above_max_value"}}
    assert llm._rejected_param(v, {"messages": [], "max_completion_tokens": 99999}) is None   # a value error
