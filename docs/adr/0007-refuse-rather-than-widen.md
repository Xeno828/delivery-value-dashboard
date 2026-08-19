# Below the evidence thresholds, refuse rather than widen the interval

When a sample falls below its threshold, the tools return a refusal naming what was needed and what was there — they do not return a wider range. The thresholds are hard, not advisory.

A wide interval says "we know this is variable"; a refusal says "we do not know this at all". Only one of them is true below the threshold, and the wide interval is the more dangerous output because it still carries a number a reader can quote. The refusal sentences end with some form of *the evidence is absent, not noisy* — that clause is the whole point and must not be trimmed.

Consequently refusals are printed verbatim by the agent, never paraphrased or softened. The thresholds themselves are listed in `docs/forecasting-agent.md` §5 and `docs/product-intake.md`.
