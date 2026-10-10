"""Task registry with template-level dev/test split.

Dev templates (24 = 3 families x 8) are used to choose prompts, labeling
rules and monitor thresholds. Test templates (60 = 3 x 20) were written
separately, checked four times, and are frozen before any test run; they do
not reuse a dev scenario. See docs/TEST_SET.md and docs/TEST_SET_DRAFT_zh.md.
"""
from __future__ import annotations

from . import code, records, reports, test_code, test_records, test_reports
from .base import TaskInstance, TaskTemplate


def dev_templates() -> list[TaskTemplate]:
    return records.templates("dev") + reports.templates("dev") + code.templates("dev")


def test_templates() -> list[TaskTemplate]:
    """60 test templates (docs/TEST_SET_DRAFT_zh.md v5). Frozen: see docs/FROZEN_TEST_SET.json."""
    return test_records.templates("test") + test_reports.templates("test") + test_code.templates("test")


def get_templates(split: str = "dev", families=None, ids=None) -> list[TaskTemplate]:
    ts = dev_templates() if split == "dev" else test_templates()
    if families:
        ts = [t for t in ts if t.family in families]
    if ids:
        ts = [t for t in ts if any(t.template_id.endswith(i) for i in ids)]
    return ts


def check_split_disjoint():
    dev = {t.template_id.split(":", 1)[1] for t in dev_templates()}
    test = {t.template_id.split(":", 1)[1] for t in test_templates()}
    overlap = dev & test
    if overlap:
        raise ValueError(f"dev/test template overlap: {sorted(overlap)}")
    return True


def get_template(template_id: str) -> TaskTemplate:
    """Look up a template by its full id, e.g. 'dev:R1_dedupe_pending'."""
    for t in dev_templates() + test_templates():
        if t.template_id == template_id:
            return t
    raise KeyError(template_id)


def get_instance(template_id: str, seed: int) -> TaskInstance:
    return get_template(template_id).instantiate(seed)
