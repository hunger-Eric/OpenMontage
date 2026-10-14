# Scene Director - Character Animation Pipeline

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


## Goal

Produce a `scene_plan` where each scene is feasible for rigged character
animation.

## Scene Planning Fields

For each scene, include:

- character IDs,
- emotional beat,
- action sequence,
- camera/framing,
- background,
- props,
- effects,
- required assets,
- transition notes.

Use `type: "character_scene"` for rigged character acting scenes. Store
character-specific detail in `character_actions`; do not put per-scene acting
data in arbitrary metadata because the shared `scene_plan` schema rejects
unknown per-scene fields.

## Complexity Budget

Prefer fewer, stronger shots:

- one establish,
- one action beat,
- one reaction beat,
- one resolution beat.

Avoid scenes that require many unique views or complex physical contact unless
the user approved that complexity.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
