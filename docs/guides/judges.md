# Configure and calibrate model judges

## Create a rubric

Rubric versions are immutable. Dimensions need observable descriptions and
bounded scales. Avoid combining unrelated properties into one score.

```json
{
  "identifier": "answer-quality",
  "version": "1.0.0",
  "title": "Answer quality",
  "instructions": "Evaluate factual correctness and direct relevance.",
  "dimensions": [
    {
      "identifier": "correctness",
      "description": "Claims agree with the supplied evidence.",
      "minimum": 1,
      "maximum": 5,
      "weight": 2
    },
    {
      "identifier": "relevance",
      "description": "The answer directly addresses the request.",
      "minimum": 1,
      "maximum": 5,
      "weight": 1
    }
  ]
}
```

Create it with `POST /api/v1/projects/{project_id}/rubrics`, then reference its
ID from a judge configuration. Credentials are not accepted in configuration;
the named provider resolves credentials from worker secret injection.

Use temperature zero unless variation is intentionally being studied. Repeated
judgments are still valuable because remote providers may be nondeterministic.
Set a cost limit, timeout, bounded retry count, and project-compatible
data-handling policy.

## Pair design

Send record keys, at least two variant IDs, judge slots, repetitions, and a
fixed seed to `/pair-designs`. Use reversed duplicates when position-bias
diagnosis justifies double cost. Assignment responses contain opaque A/B labels.

Judgment responses include verdict, confidence, every rubric score, supplied
evidence line IDs, concise justification, and abstention reason. The unique
assignment/judge constraint makes submissions idempotent at the study-cell
level.

## Calibration

Keep human-labelled calibration examples separate from examples used to write
the rubric. Report categorical metrics, confusion, kappa where applicable,
ordinal correlations, confidence Brier score, language/topic/difficulty slices,
and the exact sample counts.

Review:

- systematic false preferences by position or answer length;
- low agreement on a rubric dimension;
- malicious evidence that changes the judge;
- confidence that is higher than empirical accuracy;
- changes after judge model or prompt upgrades;
- sensitive content sent outside the approved provider boundary.

No agreement statistic proves validity. Human labels can disagree or encode
the same bias as the model judge.
