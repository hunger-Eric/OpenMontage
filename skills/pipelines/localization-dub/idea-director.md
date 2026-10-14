# Idea Director - Localization Dub Pipeline

## Direction selection before detailed design

Follow [creative intake](../../meta/creative-intake.md)'s brief text choice rule:
when a direction is not selected, present concise text options and wait for the
user. Required multi-concept work starts as text choices, not several full plans.
Expand only the chosen direction; reuse existing explicit selections. This early
choice does not replace complete scene-plan production confirmation. This rule
qualifies older descriptions below that continue internally or compare full plans.

## When To Use

Use this pipeline when the user has a source video and wants translated deliverables: subtitles, dubbed audio, or localized videos in one or more target languages.

Your first responsibility is to define what kind of localization is actually required, because subtitle-only, dubbed-audio, and lip-synced translation are different jobs.

## Runtime Selection (MANDATORY — present the constraint, don't silently pick)

Lock `render_runtime = "remotion"` (composed deliverables with per-locale caption burn / lip-sync) or `"ffmpeg"` (pure subtitle-burn over source with no composition). **HyperFrames is NOT a valid runtime on this pipeline in Phase 1** — localization depends on Remotion's caption stack and, for dubbed-with-lip-sync, on the Remotion TalkingHead pipeline.

Check Remotion availability and record the single valid Remotion choice where the schema requires it. This pipeline depends on Remotion caption and TalkingHead parity; if Remotion is unavailable, report the gap and stop.

## Reference Inputs

- `docs/localization-dubbing-best-practices.md`
- `skills/creative/short-form.md`
- `skills/creative/long-form.md`

## Process

### 1. Define The Localization Scope

Capture:

- source language,
- target languages,
- review owner,
- whether glossary or legal review is required,
- whether the user needs subtitles, dubbed audio, lip-sync, or a mix.

### 2. Classify The Source

Record the source mode:

- `single_speaker`
- `multi_speaker`
- `voiceover_led`
- `speaker_led_on_camera`

Also record whether on-screen text or motion graphics will need manual replacement or coverage.

### 3. Pick Deliverables That Match Reality

Possible deliverables:

- subtitle package only,
- dubbed video without lip sync,
- lip-synced localized video,
- per-language export bundle.

### 4. Build The Brief

Recommended metadata keys:

- `source_language`
- `target_languages`
- `deliverable_mode_map`
- `glossary_terms`
- `protected_terms`
- `review_requirements`
- `timing_risks`

### 5. Quality Gate

- localization scope is explicit,
- target outputs are realistic,
- glossary and review requirements are captured,
- risk increases from speaker count or visible mouths are surfaced.

## Common Pitfalls

- Calling every translation request a dubbing request.
- Ignoring glossary control until after audio is generated.
- Promising lip sync on visually difficult source footage without warning.

---

## Stage review

Run the existing internal review and write the stage checkpoint using the current
manifest. Complete-plan human confirmation belongs to scene_plan; this stage
does not request a second human approval. Preserve an explicitly locked legacy
run policy and any new user-requested gate.
