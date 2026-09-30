# T87 P1 authorization — v4 bounded campaign

- status: accepted
- owner: Breno
- accepted_at: 2026-09-18T19:08:02Z
- scope: five complete executions of the unmodified \`thecodacus/spec-wins\` suite
- model: qwen3.6-35b-a3b
- runtime: thecodacus/llama.cpp fork
- route: \`id=lan\`, \`http://192.168.0.125:18087/v1/chat/completions\`
- benchmark_commit: \`776e799c7e0a24271e021aca2ea4b1c1b1f10017\`
- fork_commit: \`27c54b4bbcefadedcec6397477cc2e866c1db716\`
- binary_sha256: \`37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b\`
- gguf_sha256: \`d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc\`
- seeds: \`1000, 1017, 1034, 1051, 1068\`
- task_sessions: \`t1_ratelimit\`, \`t2_metrics\`, \`t3_pipeline\`
- grader_denominator: 17 per execution (\`7 + 8 + 2\`)
- generation_budget: 330 maximum (\`5 x (13 + 27 + 26)\`)
- warmup_generation: none
- source_boundary: \`hidden/\`, \`solutions/\`, and \`docs/answer-key.md\` remain inaccessible to the model
- gpu_boundary: reserve the RTX 5090 exclusively for this llama.cpp runtime; never run beside Ollama or another runtime
- pre_generation_gate: inspect preparation, endpoint, route, model hash, binary hash, CUDA architecture, flags, GPU residency, seeds and prompt hashes before invoking \`run\`
- restrictions: no gateway/profile/catalog changes, no Herdr cleanup/reset, no extra generation calls beyond 330, no commit, no push
- interpretation: this measures the pinned Qwen3.6/runtime/protocol tuple and does not reproduce or validate the historical Qwen3.8-Flash-Next 17/17 claim

The previous invalidated P1 attempts remain historical and are not reused. This authorization covers only the bounded v4 campaign above.
