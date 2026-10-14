# Scene Director - Hybrid Pipeline

## Complete-plan confirmation

This is the shared human production-confirmation stage for automatic and manual
execution. Use the existing research/proposal/script and scene requirements;
prepare/reuse necessary actual reference images here, register their provenance,
and publish the complete standalone board using feishu_video_plan. Do not
generate video, TTS, music or a sample render before approval. Follow the shared
[visual planning flow](../../../docs/references/visual-video-planning.md).
Record board URL, source/plan hashes and execution choice in existing metadata;
checkpoint awaiting_human and stop. After the user approves that revision,
checkpoint completed with human_approved=True, then generate the whole approved
film automatically or wait for trusted manual clips in the same project.


## When To Use

You are translating the hybrid structure into a visual system that keeps the source visible and the support layers under control.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Hybrid structure and source truth |
| Tools | `frame_sampler`, `scene_detect` | Optional source inspection |
| Playbook | Active style playbook | Layout consistency |

## Process

### 1. Keep The Anchor Medium Visible

If the piece is source-led, the source must remain visually primary in the scene plan. Do not hide the anchor behind constant overlays.

### 2. Reserve Support For Clear Jobs

Use support scenes for:

- chapter transitions,
- clarifying diagrams,
- stat emphasis,
- CTA or summary moments,
- gap-filling inserts.

### 3. Plan Variant Safety

If the project needs multiple aspect ratios, define where:

- subtitles live,
- speaker labels live,
- chart or code safe zones live,
- crop-sensitive source media becomes unsafe.

### 4. Use Metadata For Balance Rules

Recommended metadata keys:

- `anchor_rules`
- `support_rules`
- `safe_zones`
- `variant_rules`
- `overlay_density_limits`

### 5. Quality Gate

- the anchor medium stays primary where intended,
- support layers are limited and purposeful,
- aspect-ratio planning is explicit,
- no scene relies on invisible future magic.

## Common Pitfalls

- Turning source-led scenes into overlay soup.
- Forgetting variant-safe zones until compose.
- Using generated inserts for every transition.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
