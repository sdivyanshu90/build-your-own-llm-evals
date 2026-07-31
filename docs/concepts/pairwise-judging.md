# Pairwise comparison and model judges

## What is being measured

Pointwise evaluation asks whether one output meets a criterion. Pairwise
evaluation asks which of two outputs better meets the same rubric. Pairwise
judgment often reduces scale-calibration differences, but it does not make the
judge objective: presentation order, verbosity, identity cues, prompt
injection, and the judge model itself can change the result.

The platform represents an outcome as `A`, `B`, `tie`, or `abstain`.
Abstentions are never converted to ties. The ordinary win rate excludes ties
and abstentions. The tie-adjusted win rate is

\[
\hat p = \frac{W + T/2}{W + L + T}.
\]

Both the numerator and denominator are reported. A result with 60 wins, 30
losses, 10 ties, and 20 abstentions therefore has tie-adjusted win rate 0.65
over 100 usable judgments, not over all 120 assignments.

## Balanced blinded assignments

`packages/evaluators/src/eval_platform_evaluators/pairwise.py`
enumerates every requested record, unordered variant pair, judge slot, and
repetition. A fixed seed shuffles design cells. The balancing invariant then
places whichever variant has appeared less often in position A; a deterministic
hash breaks exact ties. Optional reversed duplicates create a linked assignment
with A and B exchanged.

The API returns opaque display labels such as `blind:<assignment>:A`. Real
variant identities remain in the server-side assignment row. A unique database
constraint prevents the same judge from submitting a second result for the same
assignment.

Reversed duplicates diagnose order sensitivity: after resolving each blinded
verdict to the underlying winner, the decisions should agree. They are useful
but double judgment cost and may introduce dependence if the same judge
recognizes the repeated content.

## Strict judge contract

A judge configuration fixes:

- provider and model identifiers without embedding credentials;
- prompt, rubric, and response-schema versions;
- mode, repetitions, aggregation, position randomization, and seed;
- temperature, timeout, retry and repair limits;
- calibration dataset and data-handling policy;
- maximum judge cost.

The response is a `judge-response/1` object containing a verdict, every rubric
score, bounded confidence, evidence line identifiers, concise justification,
and an abstention reason when applicable. Unknown fields, unknown evidence
lines, missing rubric dimensions, and out-of-range scores fail validation.
Hidden chain-of-thought is neither requested nor stored.

## Prompt-injection boundary

Candidate outputs, references, retrieved passages, and tool results are
untrusted. `build_judge_messages` in
`packages/evaluators/src/eval_platform_evaluators/judge.py`
places the rubric and JSON schema in a trusted contract and untrusted values in
length-labelled, nonce-delimited evidence envelopes. Every evidence line gets a
platform reference such as `B:L0004`.

This is defense in depth, not proof of immunity. A model can still follow a
malicious instruction inside data. Mitigations are:

1. use a dedicated judge provider with no access to platform secrets or tools;
2. minimize data sent to the judge and redact sensitive fields;
3. require evidence references and inspect disagreement;
4. calibrate against held-out human labels;
5. test adversarial examples whenever a rubric or judge changes;
6. permit abstention rather than forcing a score.

## Repetitions and disagreement

Judgments are independently requested under repetition-specific seeds where the
provider supports seeds. Majority vote aggregates categorical decisions. Numeric
dimensions use the configured mean or median; majority mode uses the median for
numeric scores because a categorical majority is undefined for continuous
values.

Disagreement is `1 - largest_verdict_count / usable_count`. Report it beside the
aggregate. A high-confidence majority can still be unreliable when the judge is
systematically biased, so confidence is diagnostic rather than a probability
that the judgment is correct.

## Calibration and drift

Calibration reports accuracy, macro precision/recall/F1, confusion matrices,
Cohen kappa, weighted kappa for ordinal labels, rank correlations, and Brier
score when confidence is available. Kappa assumes meaningful categories and can
behave paradoxically under severe prevalence imbalance. Krippendorff alpha
supports multiple raters and missing labels but is also sensitive to the chosen
distance function.

Drift compares verdict distributions by total-variation distance, rubric-score
means, and confidence. An alert says the judge behavior changed; it does not say
which window is correct. A stable calibration set and periodic fresh human
review are still required.

## Failure modes

- A style-biased judge rewards longer answers despite an accuracy rubric.
- A candidate includes instructions that impersonate the system message.
- Reversed-order judgments disagree.
- A repair prompt changes a malformed answer into a different decision.
- Multiple repetitions are correlated because the provider ignores seeds.
- A human calibration sample is too small or unrepresentative.
- The judge provider retains data contrary to project policy.

The platform stores the exact configuration, request provenance, bounded
justification, evidence, usage, failures, and warnings needed to audit these
failure modes.
