# Sol added-context randomness check

Model: `gpt-5.6-sol`. Planned: 6 × 5 = 30 fresh requests.
HTTP attempts: 0; completed: 0.
Sampling parameters remain exactly as emitted by the existing adapter. Current adapter omits temperature, top_p, seed, reasoning effort and output-token limits; omitted means provider default, not zero or a fixed seed.
`category`, `cause`, and `action` are free text, with no discrete diagnosis enum. No dominant semantic diagnosis or consistency rate is inferred. Exact string variation is not evidence of different physical diagnoses. Review the full strings below.

| Run | Trial 1 | Trial 2 | Trial 3 | Trial 4 | Trial 5 | Exact unique causes | Exact unique actions | Exact unique structured outputs | Input hashes |
|---|---|---|---|---|---|---|---|---|---|
| 1620 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |
| 1640 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |
| 1642 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |
| 1702 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |
| 1703 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |
| 2126 | not run | not run | not run | not run | not run | — | — | — | INCOMPLETE / MISMATCH |

Counts use completed trials only; failures are not diagnoses. A full study requires every trial completed and every run's hashes matched. Dry-run contains no model output and supports no diagnosis conclusion.
`input_sha256` hashes the complete canonical JSON request including model and schema. Per-trial metadata also records exact wire-body, prompt, filtered KB and context hashes.
