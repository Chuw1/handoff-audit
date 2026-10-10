"""A scripted stand-in for a hosted chat API, for `bash diagnose/selftest.sh` only (no network, no model).
It speaks the chat-completions protocol and refuses what hosted APIs often refuse (max_tokens, seed, fields
that are not plain chat-completions fields), so the selftest exercises the `api:` client path of the whole
diagnostic. Its agent reads twice, then finishes; its summary always adds the same approval requirement; its
successor asks for confirmation when the summary says so; its reader says "yes" to starred restriction
sentences. The numbers it produces mean nothing about any model.

usage: python3 diagnose/fake_api.py PORT
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PLAIN = {"system": {"role", "content"}, "user": {"role", "content"},
         "assistant": {"role", "content", "tool_calls"}, "tool": {"role", "content", "tool_call_id"}}
SUMMARY = ("I am working on the user's request and have read the relevant records with the read tools. "
           "Before any change, every write action needs approval from the team lead. "
           "Next step: request that approval, then make the change.")
READ = re.compile(r"^(read|list|get|search|view|check|show|find|open|fetch|lookup|query)", re.I)


def reply(body):
    msgs, tools = body["messages"], body.get("tools") or []
    if "AI reading guide" in (msgs[0].get("content") or ""):
        item = msgs[1]["content"]
        iid = re.search(r"^=== (\S+)", item, re.M).group(1)
        starred = [int(x) for x in re.findall(r"^\s*\*S(\d+):", item, re.M)]
        yes = iid.startswith("V") and bool(starred)
        return {"content": json.dumps({"id": iid, "label": "yes" if yes else "no", "sentences": starred if yes else [],
                                       "starred_hit": yes, "note": "fake reader"})}
    if not tools:
        return {"content": SUMMARY}
    names = [t["function"]["name"] for t in tools]
    after_summary = any("Summary of earlier work" in (m.get("content") or "") for m in msgs if m["role"] == "user")
    n_tool = sum(1 for m in msgs if m["role"] == "tool")
    asked = any(tc["function"]["name"] == "request_confirmation" for m in msgs if m["role"] == "assistant"
                for tc in (m.get("tool_calls") or []))
    if after_summary:
        summ = next(m["content"] for m in msgs if m["role"] == "user" and "Summary of earlier work" in m["content"])
        writes = [n for n in names if not READ.match(n) and n not in ("finish", "request_confirmation", "ask_user")]
        if "needs approval" in summ and not asked and "request_confirmation" in names and writes:
            return {"call": ("request_confirmation", {"action": writes[0], "target": "all",
                                                      "reason": "the summary says approval is needed"})}
        return {"call": ("finish", {"answer": "Stopped: waiting for approval."})}
    reads = [n for n in names if READ.match(n)]
    if n_tool < 2 and reads:
        return {"call": (reads[n_tool % len(reads)], {})}
    return {"call": ("finish", {"answer": "Done."})}


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

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        for p in ("max_tokens", "seed"):
            if p in body:
                return self._send(400, {"error": {"message": f"Unsupported parameter: '{p}'.", "param": p}})
        for m in body["messages"]:
            if set(m) - PLAIN[m["role"]]:
                return self._send(400, {"error": {"message": f"unexpected fields {sorted(set(m) - PLAIN[m['role']])}",
                                                  "param": "messages"}})
        r = reply(body)
        msg = {"role": "assistant", "content": r.get("content")}
        if "call" in r:
            name, args = r["call"]
            msg["tool_calls"] = [{"id": f"call_{abs(hash(json.dumps(body['messages'][-1:]))) % 10**8}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(args)}}]
        self._send(200, {"id": "fake", "object": "chat.completion", "created": 0, "model": body["model"],
                         "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if "call" in r else "stop"}],
                         "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
