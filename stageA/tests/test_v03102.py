"""v0.3.10.2: the system-prompt variant for the F5 check (FOLLOWUP_PLAN_F5_sysprompt.md)."""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sid.agent import EpisodeConfig, _base_messages, run_episode  # noqa: E402
from sid.pipeline import cfg_from_args  # noqa: E402
from sid.runner import common_args, settings_tag, model_factory  # noqa: E402
from sid.tasks import get_instance, get_templates  # noqa: E402
from sid.tasks.base import APPROVAL_LINE_DEFAULT, APPROVAL_LINE_SCOPED  # noqa: E402


def _args(extra):
    return common_args(argparse.ArgumentParser()).parse_args(["--model", "mock:careful", "--out", "x"] + extra)


def test_default_prompt_unchanged_and_scoped_differs_in_one_sentence():
    for t in get_templates("dev", None, None) + get_templates("test", None, None):
        inst = get_instance(t.template_id, 5)
        d = _base_messages(inst, EpisodeConfig())[0]["content"]
        assert d == inst.system_prompt == inst.system_prompt_for("default")
        s = _base_messages(inst, EpisodeConfig(system_prompt="scoped"))[0]["content"]
        assert s != d and s == d.replace(APPROVAL_LINE_DEFAULT, APPROVAL_LINE_SCOPED)
        assert APPROVAL_LINE_DEFAULT in d and APPROVAL_LINE_SCOPED in s


def test_cli_flag_reaches_config_and_only_scoped_changes_job_ids():
    a0 = _args([]); a1 = _args(["--system-prompt", "scoped"])
    assert cfg_from_args(a0).system_prompt == "default" and cfg_from_args(a1).system_prompt == "scoped"
    assert "system_prompt" not in settings_tag(a0)          # default ids equal those of v0.3.10.1
    assert settings_tag(a1) == settings_tag(a0) + ",system_prompt=scoped"


def test_successor_also_gets_the_variant():
    inst = get_instance("dev:P3_confidential", 5)
    s = _base_messages(inst, EpisodeConfig(system_prompt="scoped"), summary_text="earlier work")
    assert APPROVAL_LINE_SCOPED in s[0]["content"] and s[-1]["content"].endswith("Continue the task.")


def test_mock_episode_runs_with_the_scoped_prompt():
    inst = get_instance("dev:P5_citations", 6)
    traj = run_episode(inst, model_factory("mock:careful")(), seed=3, cfg=EpisodeConfig(system_prompt="scoped"))
    assert traj["compacted"] and traj["snapshot"]["pre_messages"][0]["content"].count(APPROVAL_LINE_SCOPED) == 1
