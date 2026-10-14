# Proposal Director - Character Animation Pipeline

## Goal

Present character-animation concepts that are honest about local rigged motion,
reuse, cost, and runtime choice.

## Required Proposal Elements

Each option must include:

- characters and roles,
- visual style,
- action complexity,
- rig reuse strategy,
- sample plan,
- audio architecture,
- music plan,
- render runtime,
- cost estimate,
- honest limitation note.

## Runtime Selection

Read `skills/meta/animation-runtime-selector.md` before recommending a runtime.

For a new production, check Remotion availability and use it by default. A
character-animation pipeline selection or a rig requirement does not itself
authorize HyperFrames. Preserve HyperFrames only when an existing project is
explicitly locked to it or the user explicitly requests that runtime. If the
requested rig has no Remotion handoff, report the gap; do not silently use
HyperFrames or migrate historical assets. FFmpeg is post-processing only.

## Complete-plan confirmation

Review the complete scene-plan board and necessary references before production.
Do not generate or wait for a separate sample. Keep rig and motion QA internal.

## Cost Honesty

Local rigging is cheap at render time but expensive in authoring complexity.
Report the difference:

- asset generation cost,
- TTS/music cost,
- local render cost,
- manual complexity risk.

---

## Stage review

Run the existing internal review and write the stage checkpoint using the current
manifest. Complete-plan human confirmation belongs to scene_plan; this stage
does not request a second human approval. Preserve an explicitly locked legacy
run policy and any new user-requested gate.
