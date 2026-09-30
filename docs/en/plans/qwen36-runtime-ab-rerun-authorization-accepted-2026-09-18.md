# Qwen3.6 runtime A/B rerun authorization

- status: accepted
- owner: Breno
- accepted_at: 2026-09-18
- basis: direct owner instruction in the current llm-bench-exec pane to correct the comparison and rerun the A/B
- scope: one fresh serial A/B with the previously declared 48-generation budget
- budget: 48 generation calls total, 24 per arm
- arm_ollama: \`http://192.168.0.125:11434\`, model qwen3.6:35b-a3b
- arm_llama_cpp: \`http://192.168.0.125:18087\`, standalone Q4_K_M GGUF
- parameters: temperature=0, seed=42, num_ctx=32768, num_predict=256, 4 discarded warm-ups plus 4 prompts x 5 measured repetitions per arm
- ordering: stop the dedicated llama-server, run Ollama, unload Ollama, restart llama-server with the captured identical flags, then run llama.cpp
- precondition: a hash-addressed prompt manifest must pass the common context budget before the first warm-up
- restrictions: no extra generation calls, no gateway/profile/catalog changes, no mesh cleanup/reset, no commit, no push
- interpretation: any result is runtime plus artifact, not a pure runtime effect; the Ollama tag and standalone GGUF remain distinct artifacts
- prior_attempt: the previous run was invalidated before comparison because its context-heavy input was not accepted equivalently by both runtimes; it is not resumed or counted as this rerun

The accepted scope covers only this fresh 48-call rerun. Any retry after a failure or any larger corpus requires a new owner authorization.
