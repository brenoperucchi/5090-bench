# Explicit sampling parameters

The Flash-Next GGUF embeds sampling metadata including:

```text
general.sampling.temp = 1.000000
general.sampling.top_k = 20
general.sampling.top_p = 0.950000
```

Therefore an omitted request field is not equivalent to zero. Any future
measurement must record the values actually sent and explicitly set
`temperature`, `top_k`, and `top_p` on every request. A missing field in an
artifact is `unknown`, not an inferred default.

The current fixed-load measurements used explicit `temperature=0`,
`top_k=20`, `top_p=0.95`, `seed=42`, and `max_tokens=2048`.
