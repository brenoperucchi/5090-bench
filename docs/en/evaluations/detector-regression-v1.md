# Detector regression v1

This is a sanitized, offline regression contract for known detector failure
classes. It is not an independently labelled holdout and does not measure a
model's quality. Historical scores and `auto_score` are deliberately absent.

- Ruleset ID: `detector-regression-v1`
- Ruleset SHA-256: `911f7a04c9849fc8adcfa9b86aec0f5a1f94b325e699558d67ba52c42619799a`
- Fixture SHA-256: `e60f9d934489157d05bd7407cb5b39feda9229a29db8b6b465f501d868296cf3`

The hashes are verified by `tests/test_detector_regression.py`; edit this
document with the new hashes whenever the fixture or evaluator changes.

## Contract covered

| Detector | Regression behavior |
| --- | --- |
| Language | An English response to Portuguese fails. A marker-poor `tie` is indeterminate and never passes. |
| Escalation | Required escalation absent is `MISS`; unnecessary escalation is `LEAK`. |
| Promised action | A promise needs an explicit external delivery state and the required, sanitized Portuguese wording. Unknown delivery remains indeterminate. |
| Reasoning | Tagged reasoning, configured visible-reasoning signals, and tested plain-text openers fail. |
| Citation | Required source, exact count, source enum, fields, literal quote, quote hash, finding ID, coverage, and duplicate source IDs are checked independently. Unoffered or unread required source is indeterminate. |
| Tool | Supported name, expected call count, required arguments, and cited source must match the typed contract. |

Each case emits named outcomes with a reason code: `pass`, `fail`,
`indeterminate`, or `not_applicable`. A caller must retain those outcomes by
case and must not derive a scalar acceptance score from this suite.

The fixture contains synthetic identifiers and sanitized text only. It has no
customer prompts, ticket identifiers, endpoints, credentials, or raw model
responses.
