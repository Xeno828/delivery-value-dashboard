# Forecasts count items, never story points

Six sprints of story points is six observations, which cannot support a distribution; the same six sprints hold roughly sixty items. Item counting also cannot be inflated by estimating more generously, which point-based forecasting silently rewards.

The dashboard keeps a Points toggle for display — points remain the better lens for whether scope growth actually mattered, since item counts treat a one-line copy change and an eight-point hotfix as equal — but the forecaster reads item counts only.

This rests on one assumption: that items are roughly interchangeable in size. That assumption is the method's real weakness, so it is checked rather than trusted — `size_stability()` looks for a team splitting work smaller (which reads as speeding up when nothing got faster) and for cycle-time spread wide enough that counting loses meaning.
