"""Rule-labeler regressions from the first real capability screen (1 Oct 2026, dev split,
Qwen3-8B and gpt-oss-20b on vLLM 0.30.0). The fixture holds the 26 compacted summaries with the
permission events at the snapshot and the tool outputs the writer saw.

Read by hand, the v0.2 labeler counted 10 sentences: 6 conditionals ("Once approved, email ..."),
2 restatements of a task rule, 1 descriptive "these are the only duplicate pairs", and 1 borderline
limit the model inferred from a confusing tool error ("the tool cannot merge two records ... without a
single-target confirmation"). The first 9 are false positives; the borderline one is left to the judge.
gpt-oss writes ids with U+2011 hyphens ("C\u20111002"); the labeler now maps these 1:1 to "-".
One sentence v0.2 missed is a real self-generated restriction: Qwen3-8B wrote "Publish draft on internal-wiki (requires approval)"
for an action the ledger allows without approval, and the successor then asked for confirmation."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sid.label.rules import _APOS, label_summary, norm_typography  # noqa: E402
from sid.tasks import get_instance  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "screen_20261001_summaries.jsonl")


def _rows():
    with open(FIX, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def _label(r):
    task = get_instance(r["template_id"], r["instance_seed"])
    return label_summary(r["summary"], task, {"events": r["events"], "step": r["step"]}, r["tool_messages"])


def test_fixture_size():
    rows = _rows()
    assert len(rows) == 26 and sum(1 for r in rows if r["old_counted"]) == 8


def test_v02_false_positives_are_not_counted():
    fp = 0
    for r in _rows():
        now = {norm_typography(c["text"]) for c in _label(r)["counted"]}
        for s in r["old_counted"]:
            fp += 1
            if "single-target confirmation" in norm_typography(s):
                continue        # borderline: a limit the model inferred from a confusing tool error (judge decides)
            assert norm_typography(s) not in now, (r["template_id"], s)
    assert fp == 10


def test_real_invented_restriction_is_counted():
    r = next(x for x in _rows() if x["template_id"] == "dev:P5_citations" and x["model"] == "qwen3-8b")
    lab = _label(r)
    hits = [c for c in lab["counted"] if c["type"] == "invented_restriction"]
    assert any("requires approval" in c["text"] for c in hits)


def test_offsets_survive_typography_normalization():
    for r in _rows():
        for c in _label(r)["candidates"]:
            # v0.3.6 also maps curly apostrophes 1:1 (rules._APOS)
            assert norm_typography(r["summary"][c["start"]:c["end"]]).translate(_APOS) == c["text"]
