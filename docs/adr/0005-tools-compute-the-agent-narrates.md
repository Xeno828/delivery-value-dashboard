# The tools compute; the agent only narrates

Every figure in every agent-written report comes from a tool — `metrics.py`, `forecast.py` or `intake.py` — and the agent quotes it. The agent performs no arithmetic of its own, not even a percentage.

This is the entire trust model rather than a style preference. When a number is wrong it is wrong in one Python file and can be fixed there once for everyone; the moment the agent computes anything itself, no figure in the report is auditable and its value is gone. It is enforced structurally — the tools emit numbers, and the test suite asserts the tools agree with the dashboard's own browser-side arithmetic on the sample data.

The known liability is that duplication: two implementations of the same maths. `tests/test_agent.py` is what makes it survivable. See `docs/forecasting-agent.md`.
