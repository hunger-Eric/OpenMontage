# Idea Director - Hybrid Pipeline

## Direction selection before detailed design

Follow [creative intake](../../meta/creative-intake.md)'s brief text choice rule:
when a direction is not selected, present concise text options and wait for the
user. Required multi-concept work starts as text choices, not several full plans.
Expand only the chosen direction; reuse existing explicit selections. This early
choice does not replace complete scene-plan production confirmation. This rule
qualifies older descriptions below that continue internally or compare full plans.

## When To Use

Use this pipeline when the project combines real source media with support visuals: interviews plus diagrams, footage plus overlays, screen recording plus branded graphics, or source-led edits with generated inserts.

Hybrid is not a catch-all. Your first job is to define what stays primary.

## Runtime Selection

For new work, check Remotion and record it as the default runtime. Preserve an explicit historical lock or an explicit user request for that runtime:

1. Query `video_compose.get_info()["render_engines"]` and confirm Remotion is available.
2. Record `render_runtime: "remotion"` and the single valid choice where the schema requires a selection. Do not show a technical runtime menu or ask for another confirmation.
3. If Remotion is unavailable, report the gap and stop; do not silently substitute another runtime.

## Reference Inputs

- `docs/hybrid-video-best-practices.md`
- `skills/creative/storytelling.md`
- `skills/creative/video-editing.md`

## Process

### 1. Choose The Anchor Medium

Pick the storytelling anchor:

- `talking_head`
- `broll_footage`
- `screen_recording`
- `still_sequence`
- `narration_led_graphics`

### 2. Define Support Layers

Possible support layers:

- subtitles,
- diagrams,
- code visuals,
- stat cards,
- generated inserts,
- narration,
- music.

Each support layer should solve a specific problem, not just decorate the timeline.

### 3. Decide The Deliverable Mix

Common outputs:

- hero cut,
- vertical cutdown,
- square cutdown,
- chaptered version,
- ad variant.

### 4. Build The Brief

Recommended metadata keys:

- `anchor_medium`
- `source_inventory`
- `support_layers`
- `deliverable_mix`
- `missing_capabilities`
- `fallback_policy`

### 5. Quality Gate

- the anchor medium is explicit,
- support layers are justified,
- the deliverable mix fits the source inventory,
- missing capabilities are surfaced early.

## Common Pitfalls

- Calling everything hybrid without defining a primary medium.
- Planning support layers before understanding the source.
- Treating optional generated inserts as guaranteed.

---

## Stage review

Run the existing internal review and write the stage checkpoint using the current
manifest. Complete-plan human confirmation belongs to scene_plan; this stage
does not request a second human approval. Preserve an explicitly locked legacy
run policy and any new user-requested gate.
