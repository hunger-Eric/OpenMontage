---
name: ai-video-gen
description: Route video production requests to the OpenMontage project entrypoint. Provider selection, generation, budgets, project state and acceptance are owned by OpenMontage.
---

# OpenMontage entrypoint

For video production, work in this OpenMontage checkout and read
`docs/CURRENT_PROJECT_STATE.md`, then `AGENT_GUIDE.md`.
Use the project's current registry, selected pipeline and canonical run artifacts.
This skill is only an entrypoint: it contains no provider, model, budget,
retry or acceptance policy of its own.
Do not apply this entrypoint to unrelated standalone image or audio requests.
