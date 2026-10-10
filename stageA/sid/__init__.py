"""SID testbed: Self-originated Instruction Drift across agent context compaction.

Stage A (inference only). The package is deliberately dependency-light:
standard library + the `openai` client (for any OpenAI-compatible server
such as vLLM). Everything that touches the "outside world" is simulated.
"""

__version__ = "0.1.0"
