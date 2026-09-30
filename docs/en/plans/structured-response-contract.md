# Offline structured-response contract v1

`tools/structured_contract.py` provides a deterministic validator for a
caller-supplied response contract. It is an offline I3.2 building block. It
does not define gateway policy, rewrite responses, call a model, or produce an
aggregate quality score.

The normalized response shape has `stream_status`, `finish_reason`,
`content`, optional `reasoning`, optional `tool_calls`, and optional
`provenance`. The contract can require:

- a `json` or `text` format and a small JSON Schema subset;
- an allowed finish-reason enum;
- allowed tool names and required argument keys, including tool-only streams;
- explicit permission for reasoning-bearing streams;
- provenance entries with required string fields.

The validator returns `StructuredValidation(valid, reasons, value)`. Reasons
are named and can include incomplete stream, finish-reason, JSON parsing or
schema errors, tool name/argument errors, reasoning type/policy errors, and
provenance errors. It never returns `auto_score`, latency, or a quality label.

Required provenance rejects an absent, null, or empty list. JSON decoding is
strict about standard JSON constants and rejects decimal overflow that would
otherwise become a non-finite Python float (including `1e999`, at any nesting
depth). Finite underflow such as `1e-999` remains a valid JSON number. Enum
comparison distinguishes booleans from numbers recursively while retaining
ordinary numeric equivalence such as `1` and `1.0`. A tool-only response may
omit content, including under a JSON-format contract, only when
`allow_tool_only` is explicitly true; its tool name, arguments, and optional
tool finish reason are still checked.

Contracts and responses cross the shared JSON-safety boundary before recursive
schema checks. The boundary accepts finite JSON values and valid UTF-8,
preserves ordinary mapping subclasses as plain objects, rejects cycles and
unsupported values, and caps nesting at `MAX_JSON_DEPTH=256`. Parsed JSON
responses are normalized once more before schema validation, so escaped
isolated surrogates fail with `json_not_json` and are not returned in
`StructuredValidation.value`; malformed or excessively deep JSON remains a
named `invalid_json`/`json_not_json` result rather than a `RecursionError`.

The supported JSON Schema keywords are `type`, `enum`, `required`,
`properties`, `items`, `minItems`, `maxItems`, `minLength`, `maxLength`, and
`additionalProperties`. Unsupported keywords fail contract validation rather
than being silently ignored. This subset is an explicit offline preflight; a
consumer may require a different schema or policy and must provide that
contract before integration is claimed.

Synthetic tests cover valid and invalid JSON/schema responses, incomplete
streams, finish-reason mismatches, tool-only calls and missing arguments,
reasoning-bearing responses, required provenance, malformed contracts, and the
absence of any aggregate score field.
