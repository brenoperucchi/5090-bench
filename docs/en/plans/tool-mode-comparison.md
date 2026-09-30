# Native-tool versus JSON comparison packet v1

`tools/tool_mode_comparison.py` builds a deterministic, offline packet with
three arms for the same logical request:

- `native`: the tool is supplied through the structured tool field;
- `json`: the tool call must be a JSON envelope and the request uses JSON
  format. The system instruction contains a canonical serialization of the
  same tool name, description and parameter schema supplied to the native arm;
- `control`: no tool is supplied and the instructions forbid tool calls.

The system instructions, user prompt, model name, temperature, tool schema,
arm contract, rendered-input state and SHA-256 hashes are recorded. The
validator recomputes the fixed request and contract invariants from the mode
and tool rather than trusting a re-hashed packet. Rendered
input is `unknown` and null until a permitted client captures the actual wire
input. `can_execute` is always false in this offline builder; no arm calls a
model or endpoint.

The normalized transcript contract is deliberately stricter than a loose
success flag. Every tool call has a unique id, the expected name, an object of
arguments matching the recursively checked schema (required fields, types,
enum, string/array bounds and nested properties), and a corresponding tool
result. The final assistant turn must be the last turn, and must explicitly
list `used_tool_call_ids` for every completed result. The validator rejects
unknown tools or arguments, malformed calls, duplicate results, a result
without a call, a missing or interrupted result, and more than two call rounds.
The control arm rejects all calls. The JSON arm parses only its JSON envelope
and rejects native `tool_calls` fields; the native arm requires structured
`tool_calls` instead.

Both public validators pass inputs through one JSON-safe normalization boundary
before hashing or recursive checks. It converts ordinary mapping subclasses to
plain objects, requires string keys and valid UTF-8, rejects non-finite numbers,
unsupported values, oversized integers, cycles and structures deeper than the
fixed `MAX_JSON_DEPTH` limit (256), and preserves acyclic shared substructures.
This bound keeps later schema, comparison and hashing operations from escaping
the public error boundary through recursive copies. A malformed packet returns
`packet_not_json_serializable` and a malformed transcript or arm returns
`observation_not_json` or `arm_not_json`; neither boundary propagates
serialization or recursion errors. JSON envelopes are normalized again after
decoding, so escaped isolated surrogates in `answer` or tool calls are rejected
with a named reason instead of bypassing the UTF-8 policy. Native argument
objects therefore use the same finite JSON value domain as the JSON envelope,
including when their schema leaves an object or array open.

The validator returns named reasons in `ToolValidation` and never assigns a
quality score. A valid transcript proves contract and sequence adherence only;
quality, latency, and model preference require a separately approved run and
independent labels.
