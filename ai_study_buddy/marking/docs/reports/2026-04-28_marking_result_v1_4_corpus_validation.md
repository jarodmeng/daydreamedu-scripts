# Marking Result v1.4 Corpus Validation (2026-04-28)

Validator path:

- `ai_study_buddy.marking.core.artifact_schema.validate_marking_artifact_dict`

Scope:

- `ai_study_buddy/context/marking_results/**/*.json`

Summary:

- Total files scanned: `154`
- Version breakdown:
  - `marking_result.v1.4`: `154`
- Validation failures: `0`

Notes:

- During strict-schema rollout, telemetry shape differences were observed and normalized into explicit schema fields under `generation.telemetry` while keeping closed-contract behavior (`additionalProperties: false`).
