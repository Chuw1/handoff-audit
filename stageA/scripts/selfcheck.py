"""Run the mock test suite without pytest (e.g. inside the vLLM container on the cluster).

  apptainer exec ~/vllm.sif python3 scripts/selfcheck.py
"""
import inspect
import pathlib
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")


class _MP:
    """Minimal stand-in for pytest's monkeypatch (setenv only)."""
    def __init__(self):
        self.saved = {}

    def setenv(self, k, v):
        self.saved.setdefault(k, os.environ.get(k))
        os.environ[k] = v

    def undo(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main():
    import test_end_to_end_mock as t1
    import test_labeler_cases as t3
    import test_openai_client as t2
    import test_regressions as t4
    import test_dev_regressions as t9
    import test_labeler_v03 as t8
    import test_screen_regressions as t7
    import test_test_split as t5
    import test_v03 as t6
    import test_v039 as t10
    import test_v03101 as t11
    import test_v03102 as t12
    import test_v03103 as t13
    fails = 0
    n = 0
    for mod in (t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13):
        for name, fn in sorted(vars(mod).items()):
            if not (name.startswith("test_") and callable(fn)):
                continue
            params = inspect.signature(fn).parameters
            runs = [{}]
            if "static" in params:
                runs = [{"static": "0"}, {"static": "1"}]
            for kw in runs:
                n += 1
                mp = _MP()
                try:
                    if "monkeypatch" in params:
                        kw = {**kw, "monkeypatch": mp}
                    if "tmp_path" in params:
                        with tempfile.TemporaryDirectory() as d:
                            fn(tmp_path=pathlib.Path(d), **kw)     # pytest passes a Path too
                    else:
                        fn(**kw)
                    print(f"ok    {name} {kw.get('static', '')}")
                except Exception:
                    fails += 1
                    print(f"FAIL  {name}")
                    traceback.print_exc()
                finally:
                    mp.undo()
    print(f"\n{n - fails}/{n} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
