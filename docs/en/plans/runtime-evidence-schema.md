# Runtime evidence snapshot v1

`tools/runtime_snapshot.py` defines the offline shape used by a permitted
runtime capture. It does not inspect a process or make a claim about the
current machine.

The top-level `schema_version` is `runtime-snapshot-v1`. Every section has
explicit fields for process identity, server identity, model identity, and GPU
state. A missing value is `null`; it is not copied from a configuration file or
inferred from another field. `status` is `unknown` until at least one observed
field is present, and `known` only means that the snapshot contains an
observation.

| Section | Evidence fields |
| --- | --- |
| `process` | `pid`, `listener`, `command_line`, `binary`, `binary_sha256` |
| `server` | `version`, `endpoint`, `settings`, `log_path`, `logs` |
| `model` | `name`, `digest`, `runner`, `layers` |
| `gpu` | `memory_used_bytes`, `memory_free_bytes`, `residency`, `spill` |

`validate_snapshot()` checks the schema and rejects negative counters,
booleans used as integers, malformed strings, malformed sections, and an
unknown schema version. Flexible evidence such as listener details, effective
settings, log excerpts, residency records, and spill diagnostics may be a
string, list, mapping, or boolean because their concrete shape belongs to the
runtime collector. The validator does not turn any of those values into a
residency conclusion. Both validation and normalization pass through the
shared JSON-safety boundary: cycles, unsupported values, invalid UTF-8 and
structures deeper than `MAX_JSON_DEPTH=256` return `snapshot_not_json` from
validation and raise `ValueError("snapshot_not_json")` from normalization.
A finite JSON root with the wrong type raises
`ValueError("snapshot_not_object")`. The normalizer reserves its explicit
all-unknown snapshot for absence (`None` or `{}`), so malformed evidence
cannot be silently relabeled as an unobserved runtime. It also applies the
snapshot schema before overlaying fields: an explicit wrong version raises
`ValueError("snapshot_schema_version")`, and other schema violations raise
`ValueError("snapshot_schema")`. The validator uses the same stable root and
version reasons. Unknown top-level or section keys are schema violations rather
than silently discarded, and `captured_at` must be a non-empty string when
present. No `copy.deepcopy` hook is used; the bounded normalizer performs its
own finite traversal, and invalid data cannot fail only during later
serialization.

The offline tests cover an all-unknown snapshot, partial observations without
filling omissions, all four evidence sections, and malformed roots, versions,
unknown keys, timestamps, and numeric values. Live PID, listener, endpoint,
binary, digest, logs, memory, and residency remain unknown until an approved
capture.
