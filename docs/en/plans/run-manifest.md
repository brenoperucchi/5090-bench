# Campaign and run manifest v1

`tools/run_manifest.py` builds a hash-addressed record for a benchmark or
diagnostic. It is bookkeeping only and performs no model, server, network, or
GPU operation.

Each manifest contains unique generated `campaign_id` and `run_id` values,
the model name, and lowercase SHA-256 values for the executable code, system
prompt, goldset, serialized payload, and canonical options. `cache_state` is
explicitly one of `cold`, `warm_uncached`, `warm_cached`, or `unknown`.

`validate_manifest()` rejects missing or malformed IDs, hashes, model names,
schema versions, and cache states. `write_manifest()` uses exclusive file
creation, so an existing run cannot be silently overwritten. The writer also
requires an existing parent directory; creating an evidence tree is an
explicit caller action.

The tests cover generated-ID uniqueness, all required hashes, invalid IDs and
hashes, cache-state validation, round-trip JSON, and the exclusive-write
collision path. A manifest records declared inputs and does not prove that a
runtime used them; that evidence belongs in the runtime snapshot and recorder
records.
