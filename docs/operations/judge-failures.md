# Judge-output failure response

An elevated strict-validation failure often follows a judge model, prompt,
schema, or provider structured-output change.

1. Stop or pause judge work before bounded repairs create unnecessary cost.
2. Slice failures by judge configuration, prompt version, provider, and error.
3. Inspect sanitized raw artifacts under approved access; never log them.
4. Re-run adversarial and calibration fixtures with the deterministic fake and
   affected adapter.
5. Create new prompt/rubric/judge versions; never mutate completed provenance.
6. Canary the replacement and compare disagreement, calibration, and cost.

Do not relax the response schema merely to improve completion rate. That can
turn malformed judgments into silently wrong scores.
