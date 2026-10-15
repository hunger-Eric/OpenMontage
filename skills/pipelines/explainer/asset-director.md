# Asset Director — Explainer Pipeline

## Project generation defaults

Follow `AGENT_GUIDE.md > Project-owned generation route`. Inspect portable
selectors, configured personal preferences and actual session capabilities.
Use the approved tool/provider/model; native images are optional and their
availability must be checked in the actual session. Register all outputs and
provenance. Never switch route after a provider failure without authorization.

## When to Use

For faithful replicas, follow `skills/meta/reference-production-handoff.md`'s
registered `video_trimmer(reference_clip)` -> `VideoSelector` binding. Generate
from the corresponding actual source segment, not just a described still. Keep
optional identity references from overriding camera/framing. Review action,
composition, internal cuts and embedded text against actual source media. Reuse
accepted leaves and retain unknown attempts; original authorized audio is a
separate layer, not a new TTS/music request.

You are the Asset Producer for a generated explainer video. You have a `scene_plan` with required assets and a `script` with narration text. Your job is to generate every asset needed: narration audio, images, diagrams, code snippets, and background music. Every file must exist on disk before you finish.

This is where plans become real files. A missing or low-quality asset will torpedo the final video.

## Animation authoring — which runtime

Before authoring any animated Remotion component for this pipeline, read **`skills/meta/animation-runtime-selector.md`**. It's the routing authority for deciding between Remotion primitives and GSAP plugins.

Quick routing for common explainer needs:

| Scene type | Recommended approach |
|---|---|
| Title card, fade, slide, scale | Remotion primitives — `interpolate()` + `spring()` |
| Word-level caption highlight synced to narration | Existing `CaptionOverlay` component (already in `remotion-composer/src/components/`) |
| Per-character kinetic typography ("words explode in one letter at a time") | GSAP SplitText — read `.agents/skills/gsap-plugins/SKILL.md` |
| Multi-step choreography across 4+ tweens | GSAP timeline — read `.agents/skills/gsap-timeline/SKILL.md` |
| Logo build (line drawing, stroke reveal) | GSAP DrawSVG — read `.agents/skills/gsap-plugins/SKILL.md` |
| Data chart (bar/line/pie/KPI) | Remotion built-in chart components — see `remotion-composer/SCENE_TYPES.md` |
| Terminal or CLI demo | Remotion TerminalScene — read `.agents/skills/synthetic-screen-recording/SKILL.md` |

**The keep-it-simple bias:** if Remotion primitives solve a scene in ≤ 20 lines, use them. Only pull in GSAP when the plugin genuinely earns its bundle weight.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | What to produce |
| Playbook | Active style playbook | Image prompts, diagram style, audio preferences |
| Tools | `tts_selector`, `image_selector`, `video_selector`, `diagram_gen`, `code_snippet`, `music_gen` — selectors auto-discover all available providers from the registry | Generation capabilities |
| Cost tracker | `tools/cost_tracker.py` | Budget governance |

## Process

### Reuse, recovery and overlapping preparation

Follow `AGENT_GUIDE.md`'s bounded multi-shot path. Reuse the run capability
snapshot and approved references; inspect the original task/attempt receipt
before polling or recovering a failed/unknown call. Never start another paid
attempt merely because a session ended. Keep accepted siblings immutable.
While approved media jobs run, prepare one project-local composition/edit
workspace and hand it to edit/compose; do not rebuild it at each stage.
Pending media may be placeholders during authoring only. This preparation
cannot complete downstream checkpoints or bypass actual-media review. Flow
submissions remain serial on its shared browser profile. Record explicit
preparation/recovery/handoff intervals with `scripts/workflow_timing.py`.

### Step 1: Inventory Required Assets

For reference-driven work, read `skills/meta/reference-production-handoff.md`
and the approved adaptation referenced by the scene plan. Generate from its
speech architecture and per-shot performance/continuity notes. Include the
previous and next passage's context in the delivery instructions; quote only
the current intended dialogue as spoken text. Use action-specific gestures and
continuing poses rather than the same opening, generic hand motion and closing
smile in every request.

Walk every scene in the scene plan. For each `required_assets` entry, create an asset task:

```
Asset Task:
  scene_id: scene-3
  type: diagram
  description: "Mermaid flowchart: query -> encode -> search -> rank -> return"
  source: generate
  tool: diagram_gen
  estimated_cost: $0.00
```

Also create tasks for:
- **Narration audio** — coherent passages with one selected voice/delivery setup for external narration; use provider-sized chunks only where needed, retaining neighboring context. Native dialogue comes from its video assets, not an additional TTS track. For pure-Chinese Omni/Flow native-speaking assets, follow `docs/references/omni-chinese-redub.md`: independent Chinese TTS and phrase/pause alignment are mandatory while preserving the picture. Pure English and mixed-language assets retain native audio and skip that redub/alignment branch.
- **Background music** — one track for the whole video (use `music_gen` or select from library)
- **Sound effects** — per playbook's `sfx_style` (optional, use `music_gen` or stock)

### Step 2: Check Budget

Before generating anything:
1. Record available cost estimates; keep unknown credit prices as unknown.
2. Check only explicit user caps and real provider/account constraints. An absent
   cap is not a blocker and must not trigger another fee-confirmation question.
3. Music already included in the approved full plan is authorized with that plan.
   For Flow, pass `confirm_paid_generation=true` and omit the credit cap (or use
   null) unless the user specified one; retain the transport authorization check.
4. If a real explicit cap or provider constraint blocks execution, record it and
   request direction for the affected item. Do not silently remove planned music,
   reduce shots or switch providers to work around it.

### Generate the approved full plan

After the complete scene-plan board is approved for automatic production,
generate the planned assets and continue internal review and post-production.
Do not create a separate approval sample or wait for another assets approval.
The first planned shot may be reviewed internally before continuing with the
remaining shots. It is part of the full film, not an extra sample or human gate;
approval of the complete plan remains sufficient for unchanged production.
For manual production, preserve the plan and wait for trusted returned clips;
for plan-only delivery, stop without video/audio generation. Review each real
asset and repair only failed leaves; changes outside the approved plan require
user direction.

### Step 2c: Model Video Contract and Continuation

For every model-generated video asset, read
`proposal_packet.production_plan.video_generation_contract` before submitting.
The provider's per-call frame/duration/aspect envelope is a shot-planning input,
not a reason to stop the whole production. Split long productions into planned
shots and keep generating until every delivery clip is accepted.

For Agnes, call `video_selector(operation="discover_models", preferred_provider="agnes")` before each new
production. The executing agent chooses an eligible model using the live
catalog, plan entitlement, relevant task receipts and creative requirements;
listing alone does not prove access. Pass its exact `model` explicitly and
freeze that choice in `video_generation_contract`. No user version-choice
question is needed within the authorized provider/plan/spending scope.
For 2.5/Flash use integer 4–12-second clips and `size`/`aspect_ratio`; Flash is
720P with up to 5 images, 3 audio references and no video reference. Use
`keyframe` for first/last frames and `reference` for image/audio references;
do not pass legacy frame/width/FPS fields. Ordinary 2.5 requires explicit
paid-route authorization (`allow_paid_model=true`) before a new submission.
Legacy v2.0 retains its 9–441 (`8n + 1`) frame contract only for an explicit
eligible selection or recovery, with `aspect_mismatch_policy` for image modes.
Unknown model contracts stop before upload or generation. On an access failure,
preserve evidence; never silently change models/providers or escalate billing.

Before the first submission, validate every reference transport once. A local
file must be readable and hashable; a remote URL must return success, the
expected image content type, and a non-empty body. Prefer an already proven
direct URL from the same run over another upload. Record the validated URL/file
identity in the request receipt so later shots reuse evidence rather than
retesting or changing hosts.

Each output path owns a stable `attempt_id`, request fingerprint, provider task
ID, and append-only attempt ledger. On interruption or ambiguous status, resume
or poll that provider task; do not submit a duplicate. Create a new attempt only
after the previous provider task is terminal-failed. Do not switch models or
providers silently.

Review the first generated clip from its actual decoded media before batch
continuation. A model (not a deterministic heuristic) must evaluate identity,
required action, continuity, and reference alignment and persist the receipt in
`asset_manifest.assets[].semantic_review`. A failed review is regenerated. An
approved deviation must be written to `decision_log` as
`category: "semantic_adaptation"` and propagated into the script/scene plan
before downstream work continues.

When that first-shot gate passes, freeze the accepted provider request shape,
the observed source dimensions, and one declared normalization rule. Generate
the remaining independent shots as a bounded batch (maximum 2-3 concurrent
provider tasks when supported; otherwise serial), keeping a unique stable
`attempt_id` per output. Poll each task to terminal status. Normalize/decode the
accepted outputs together and build one aggregate review surface. Do not repeat
per-shot environment discovery, URL upload, or normalization experiments.

Build the asset manifest from the persisted request/result receipts, hashes,
media probes, and semantic-review records. Before checkpointing, validate the
complete manifest against its schema. Repair only a failed leaf with a changed
request; do not regenerate accepted siblings.

### Step 3: Generate Narration

For pure-Chinese Omni/Flow native dialogue, use the generated video audio as
the timing reference, then follow the redub workflow cited above: independent
Chinese TTS replacement and phrase/pause alignment are mandatory, with the
TTS and alignment receipts registered. For English or mixed-language native
dialogue, retain the original audio and skip redubbing, transcription,
synchronization, and listening-specific checks unless the user separately
requests captions or another explicit text/audio deliverable. This TTS
procedure applies to external narration. Group connected sections into
coherent spoken passages within the selected provider's limits. Keep the
chosen voice and settings stable, preserve section delivery cues inside each
passage, and map cues to the generated narration's actual timestamps rather
than making each section a separate performance with its own restart.

For each planned narration passage:
1. Extract the narration text
2. Read `script.voice_performance` and section `delivery_cues`
3. Use `delivery_cues.provider_text` when present; otherwise transform the section text with purposeful punctuation and break tags only when the selected provider supports them
4. Apply speaker directions from the script (pace, emphasis, emotion)
5. Apply the playbook's `audio.voice_style`
6. Map cues to provider parameters:
   - OpenAI: `instructions` only with `model: "gpt-4o-mini-tts"`; use `response_format` for output format
   - Google TTS: `input_type: "ssml"` when using `<break>` tags, plus `speaking_rate` in `0.25..2.0` and `pitch` in `-20..20`
   - ElevenLabs: `stability`, `similarity_boost`, `style`, `speed`, and `use_speaker_boost`
   - Azure: voice aliases (`andrew`, `brandon`, `ava`, `guy`, `jenny`) or any Azure short name, SSML `rate` (e.g. `"-4%"`), `pitch` (e.g. `"+1st"`), and `style` (e.g. `"narration-professional"`) — see the `azure-text-to-speech` skill
7. Generate using `tts_selector` — it auto-routes to the best available TTS provider based on user preference and availability. Check the registry's `best_for` fields to understand each provider's strengths.
8. Record the applied `voice_performance` metadata on each narration asset
9. Verify the audio file exists and duration matches expected timing (±15%)
10. Transcribe the generated narration itself and compare that transcript with
    the approved script. A provider success response, valid PCM, plausible
    duration, or `provider_text_used=true` does not prove what was spoken.
    Missing transcription or a transcript-to-script match below 90% blocks the
    asset checkpoint.
11. Generate subtitle cues from the verified final narration transcript and
    its timestamps. Never use script-timing projection as the subtitle source
    for a generated voice track.

**Narration timing is not a license to stretch speech.** If the generated read
misses the planned duration by more than 15%, revise the script/scene timing or
regenerate with a provider-supported speaking-rate control. Do not use global
post-generation `atempo` merely to fill the visual timeline. Tempo ratios are advisory indicators; judge the intended performance by
listening. Enforce a numerical minimum only when the production declares it
in `audio_review_policy`, rather than asking for a separate generic approval. A provider that receives only verbatim
text and a voice name has not applied section-level delivery cues — record
`delivery_cues_applied: false` instead of inferring approval from decode success.

**Pronunciation guide**: If the script contains technical terms, jargon, or names with non-obvious pronunciation, include a pronunciation map in the TTS request.

**Flat voice failure:** If the approved voice sounds monotone, robotic, rushed,
or ignores intended pauses, do not batch the remaining sections. Revise the
`voice_performance` parameters within the confirmed plan and repair that actual section; do not request a separate sample approval.

### Step 4: Generate Visual Assets

Process asset tasks grouped by tool for efficiency:

**Images (`image_selector`)**:
1. Build the prompt from the scene's actual purpose:
   - scene-specific shot/lighting/texture cues from `shot_language`, `shot_intent`, and `texture_keywords`
   - an adapted visual anchor from the playbook or custom identity
   - the concrete subject/action/environment
   Use `lib/shot_prompt_builder.py` when helpful.
2. Add negative prompt from playbook
3. Include consistency anchors (same character/world/palette family), but do NOT reuse the exact same phrasing for every image
4. Generate and verify the file exists
5. If the result doesn't match expectations, refine the prompt and regenerate (max 2 retries)

**Diagrams (`diagram_gen`)**:
1. Convert the scene description into valid Mermaid syntax
2. Apply playbook's `asset_generation.diagram_style`
3. Generate SVG/PNG
4. Verify all nodes and edges are present

**Code snippets (`code_snippet`)**:
1. Extract language and code from the scene description
2. Apply syntax highlighting theme from playbook's overlay styles
3. Generate highlighted image or Remotion-compatible data

### Step 5: Prepare The Approved Music

Follow [the background music workflow](../../../docs/references/music-workflow.md).

1. Read the proposal's music choice, `metadata.music_plan` where present, and the
   playbook's music direction. Reuse accepted music; do not select a new provider
   or track simply because this stage has started.
2. If the choice is unresolved, follow `AGENT_GUIDE.md > Music Plan`: user library,
   configured search options, generation options, supplied music or no music.
   Check current availability and the stage manifest before using a tool. A
   source failure is not permission to move to a different source or paid API.
3. Acquire only the approved music. A deliberate no-music choice needs no music
   file; an unavailable required source must be reported with its reason in
   `asset_manifest.metadata`, rather than silently omitted.
4. Register the actual path, measured duration, provider/tool and applicable
   license/attribution. Do not rename an arbitrary audio format to `.mp3`.
5. Hand duration limits to edit: choose source ranges, natural looping or other
   sections as appropriate to the content. Do not silently leave looping to
   compose or impose a fixed soundtrack duration/model.

If required music cannot be obtained, report the gap at this stage.

### Step 6: Build Asset Manifest

Assemble all generated assets into the manifest:

```json
{
  "version": "1.1",
  "assets": [
    {
      "id": "narration-s1",
      "type": "audio",
      "subtype": "narration",
      "path": "assets/narration/s1.mp3",
      "source_tool": "tts_selector",
      "scene_id": "scene-1",
      "duration_seconds": 8.2,
      "cost_usd": 0.003
    },
    {
      "id": "img-scene-3",
      "type": "image",
      "path": "assets/images/scene-3-diagram.png",
      "source_tool": "diagram_gen",
      "scene_id": "scene-3",
      "cost_usd": 0.00
    },
    {
      "id": "music-bg",
      "type": "audio",
      "subtype": "music",
      "path": "assets/music/background.mp3",
      "source_tool": "music_gen",
      "duration_seconds": 62,
      "cost_usd": 0.05
    }
  ],
  "total_cost_usd": 0.053,
  "generation_summary": {
    "narration_sections": 5,
    "images_generated": 8,
    "diagrams_generated": 2,
    "music_tracks": 1
  }
}
```

### Pre/Post Self-Review for Generation Prompts

> Before sending a prompt to any generation tool — `image_selector`, `diagram_gen`, `video_selector`, even `code_snippet` styling prompts — run a three-step self-review modeled on the CHAI oversight loop ("Building a Precise Video Language with Human-AI Oversight", arXiv 2604.21718v2). Cost is small (no extra tool calls); benefit is large (avoids wasted generations). This applies just as strongly to `diagram_gen` Mermaid prompts and `image_selector` illustration prompts as it does to video generation — bad explainer visuals fail in the same way: missing subject, missing framing, vague "make it look educational."
>
> **Step 1 — Pre-caption pass.** Write the prompt the way you'd write it today. Do not over-edit; aim for a complete first draft.
>
> **Step 2 — Critique pass.** Score the draft against the 5-aspect checklist (Subject / Subject Motion / Scene / Spatial Framing / Camera). For each aspect:
> - Is it specified? If not, is the omission deliberate (e.g., "Camera N/A — Remotion native scene", "no subject motion — static diagram") or accidental?
> - Are confusable terms disambiguated? (dolly vs zoom, pan vs truck, bird's-eye vs aerial, fisheye vs barrel, full shot vs close-up; for diagrams: flowchart vs sequence vs state diagram, top-down vs left-right)
> - Are emotional adjectives ("clean", "professional", "modern") replaced with their visual causes (sans-serif typography, generous whitespace, monochromatic palette with one accent)?
> - For multi-shot prompts: is identity anchored verbatim across shots? For `image_selector` prompts that recur (a character or world appearing in multiple scenes), are consistency anchors specified verbatim?
>
> **Step 3 — Post-caption pass.** Rewrite filling the missing aspects, fixing confusable terms, and replacing subjective language. The post-caption is what gets sent to the generation tool.
>
> Log the (pre, critique, post) triplet in the asset metadata for traceability. This mirrors the CHAI workflow and creates a record the reviewer can audit.

### Step 7: Verify All Assets

**Existence check:**
- [ ] Every asset `path` exists on disk
- [ ] Every narration section has a corresponding audio file
- [ ] Final narration has a persisted transcript and matches the approved script at ≥90%
- [ ] Subtitle text and timing are derived from that verified transcript
- [ ] Every scene with `required_assets` has all assets generated
- [ ] Background music file exists
- [ ] Every generated video records attempt_id, provider_task_id, request_fingerprint, and attempt_ledger_path
- [ ] Interrupted/ambiguous provider tasks were resumed rather than re-submitted

**Quality check:**
- [ ] Narration durations within ±15% of expected timing
- [ ] Narration assets record `voice_performance.delivery_cues_applied`
- [ ] Generated narration uses the confirmed provider, voice and performance settings and passes internal review
- [ ] Images match the playbook's style (review consistency anchors)
- [ ] Diagrams are legible and complete
- [ ] Total cost within budget
- [ ] Token Plan usage is recorded as null when unknown, never as zero USD
- [ ] Every generated motion asset has a model-owned semantic review receipt

### Step 8: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Completeness** | Does every scene have all required assets? |
| **Audio quality** | Does narration sound natural with correct pacing? |
| **Visual consistency** | Do all images look like they belong to the same video? |
| **Budget adherence** | Is total cost within the approved budget? |
| **Playbook fidelity** | Do assets match the playbook's style guide? |

If any dimension scores below 3, fix before proceeding.

### Step 9: Submit

Validate the asset_manifest against the schema and persist via checkpoint.

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- **Generating before checking budget**: Always estimate total cost first. A 60-second video with 15 images can burn $3+ quickly.
- **Inconsistent image style**: Each image_selector call is independent. Use consistent anchors, but adapt them per scene. If you paste the same style prefix into every prompt, the video will feel machine-made and repetitive.
- **Ignoring narration timing**: If TTS produces 12s of audio for a 10s section, the edit phase will struggle. Check durations.
- **Ignoring delivery cues**: Generating raw script text when `provider_text` or `delivery_cues` exist will flatten the read. Apply the voice-performance contract first.
- **Missing pronunciation guide**: "PostgreSQL" or "Kubernetes" will be mispronounced without explicit guidance.
- **One retry then give up**: If an image doesn't match, refine the prompt specifically — don't just retry the same prompt.
- **AI-generating images with exact text (CTA, business names, contact info)**: AI image models frequently hallucinate wrong text — wrong business name, wrong phone number, misspelled words. **Never use AI image generation for scenes where text must be verbatim.** Use Remotion `text_card` type instead. This applies to: CTA screens, title cards with business names, contact info overlays, legal disclaimers. If a scene's `type` is `text_card` in the scene plan, do NOT generate an image for it — skip it and let the compose stage render it natively in Remotion.


## When You Do Not Know How

If you encounter a generation technique, provider behavior, or prompting pattern you are unsure about:

1. **Search the web** for current best practices — models and APIs change frequently, and the agent's training data may be stale
2. **Check `.agents/skills/`** for existing Layer 3 knowledge (provider-specific prompting guides, API patterns)
3. **If neither helps**, write a project-scoped skill at `projects/<project-name>/skills/<name>.md` documenting what you learned
4. **Reference source URLs** in the skill so the knowledge is traceable
5. **Log it** in the decision log: `category: "capability_extension"`, `subject: "learned technique: <name>"`

This is especially important for:
- **Video generation prompting** — models respond to specific vocabularies that change with each version
- **Image model parameters** — optimal settings for FLUX, GPT Image, Imagen differ and evolve
- **Audio provider quirks** — voice cloning, music generation, and TTS each have model-specific best practices
- **Remotion component patterns** — new composition techniques emerge as the framework evolves

Do not rely on stale knowledge. When in doubt, search first.

---

## Stage review

Run the existing internal review and write the stage checkpoint using the current
manifest. Complete-plan human confirmation belongs to scene_plan; this stage
does not request a second human approval. Preserve an explicitly locked legacy
run policy and any new user-requested gate.
