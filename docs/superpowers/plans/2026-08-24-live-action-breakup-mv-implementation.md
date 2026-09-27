# 《迟到的戒指》真人剧情 MV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified 9:16, approximately 70-second, live-action Chinese narrative MV from approved photoreal stills, eight Google Flow ten-second source clips, one original Chinese female-vocal song, and a Remotion final composition that selects 6 seconds from the hospital clip and 4 seconds from the final ring-pickup clip.

**Architecture:** Canonical OpenMontage cinematic artifacts and checkpoints own the production state under `projects/late-ring-live-action-mv/`. Codex image generation owns photoreal character and scene anchors; Google Flow MCP owns motion video and music; Remotion and FFmpeg own deterministic composition and validation. Human gates separate still approval, sample approval, full-asset approval, and final export approval.

**Tech Stack:** OpenMontage cinematic pipeline, Codex image generation, `google_flow_mcp_video`, `google_flow_mcp_music`, Remotion, FFmpeg/ffprobe, JSON Schema checkpoints.

## Global Constraints

- Work in the existing `E:\project\OpenMontage` checkout; do not create or switch branches or worktrees.
- Preserve all existing dirty and untracked files outside this production project.
- Use `cinematic` pipeline, `renderer_family="cinematic-trailer"`, `render_runtime="remotion"`, and `composition_mode="atelier"`.
- Output is 9:16 vertical, approximately 70 seconds, made from eight real-motion source clips of approximately 10 seconds each and final selected durations `[10,10,10,10,10,10,6,4]`.
- Characters are photoreal Chinese adults; anime, illustration, 3D-cartoon, celebrity likeness, plastic skin, malformed hands, and identity drift fail closed.
- Codex generates all approved character/scene stills before Google Flow video or music calls.
- Google Flow MCP is the only approved video and music provider. Do not silently switch to Grok or another model.
- Before every Google Flow call, report the exact tool, provider, visible model/variant, purpose, sample/batch status, and displayed credit cost; wait when new credit authorization is required.
- Do not replace failed motion with still-image pan/zoom.
- Remotion performs composition; FFmpeg performs mechanical post-processing and validation only.
- Black-diffusion treatment decreases from memory to reality: approximately 1/4 in warm memories, 1/8 at the doorway, and minimal in the hospital.
- No external publication, Git commit, push, deployment, or additional provider spend without separate authorization.

---

## File Structure

- Create: `projects/late-ring-live-action-mv/project.json` — canonical project marker created by `init_project`.
- Create: `projects/late-ring-live-action-mv/artifacts/video_analysis_brief.json` — verified reference evidence and five-aspect analysis.
- Create: `projects/late-ring-live-action-mv/artifacts/research_brief.json` — cited visual, technique, and capability research.
- Create: `projects/late-ring-live-action-mv/artifacts/proposal_packet.json` — three concepts, selected concept, provider/runtime/music plan, costs, and approval.
- Create: `projects/late-ring-live-action-mv/artifacts/decision_log.json` — append-only decisions for pipeline, concept, providers, runtime, composition mode, music, motion, and approvals.
- Create: `projects/late-ring-live-action-mv/artifacts/script.json` — approved dialogue, lyrics, music turns, and 70-second beat map.
- Create: `projects/late-ring-live-action-mv/artifacts/scene_plan.json` — eight source scenes with five-aspect cinematography, selected final intervals, and transition contracts.
- Create: `projects/late-ring-live-action-mv/artifacts/character_consistency.json` — project-local identity, wardrobe, prop, lighting, and forbidden-change contract.
- Create: `projects/late-ring-live-action-mv/artifacts/still_generation_plan.json` — thirteen still deliverables and dependency order.
- Create: `projects/late-ring-live-action-mv/assets/reference/` — downloaded reference media and selected frames.
- Create: `projects/late-ring-live-action-mv/assets/stills/characters/` — character sheets and shared-scale reference.
- Create: `projects/late-ring-live-action-mv/assets/stills/scenes/` — doorway, happy-memory, ring-transition, and hospital anchors.
- Create: `projects/late-ring-live-action-mv/assets/music/` — approved Google Flow song and receipt metadata.
- Create: `projects/late-ring-live-action-mv/assets/video/` — source units 01–08 and per-call receipt metadata.
- Create: `projects/late-ring-live-action-mv/assets/sample/sample_v1.mp4` — approved 20-second doorway sample ending on the ring-drop/music transition.
- Create: `projects/late-ring-live-action-mv/artifacts/asset_manifest.json` — schema-valid inventory with provider/model/cost evidence.
- Create: `projects/late-ring-live-action-mv/artifacts/edit_decisions.json` — exact 70-second timeline, transitions, audio, and grade.
- Create: `projects/late-ring-live-action-mv/remotion/index.tsx` — atelier composition entry.
- Create: `projects/late-ring-live-action-mv/remotion/LiveActionBreakupMV.tsx` — project-local video-led composition.
- Create: `projects/late-ring-live-action-mv/remotion/continuity.ts` — typed scene timing, audio, crop, and transition constants.
- Create: `projects/late-ring-live-action-mv/renders/final.mp4` — final vertical master.
- Create: `projects/late-ring-live-action-mv/artifacts/render_report.json` and `final_review.json` — runtime and user-path acceptance evidence.

### Task 1: Initialize Canonical Project and Materialize Approved Preproduction

**Files:**
- Create: `projects/late-ring-live-action-mv/project.json`
- Create: `projects/late-ring-live-action-mv/artifacts/video_analysis_brief.json`
- Create: `projects/late-ring-live-action-mv/artifacts/research_brief.json`
- Create: `projects/late-ring-live-action-mv/artifacts/proposal_packet.json`
- Create: `projects/late-ring-live-action-mv/artifacts/decision_log.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_research.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_proposal.json`

**Interfaces:**
- Consumes: approved design at `docs/superpowers/specs/2026-08-24-live-action-breakup-mv-design.md` and verified reference analysis.
- Produces: schema-valid proposal state used by `script`, `scene_plan`, and all downstream checkpoints.

- [ ] **Step 1: Verify no existing project identity conflicts**

Run:

```powershell
Test-Path -LiteralPath 'E:\project\OpenMontage\projects\late-ring-live-action-mv\project.json'
```

Expected: `False`. If `True`, read checkpoints and resume; do not overwrite.

- [ ] **Step 2: Initialize the canonical project**

Run:

```powershell
$env:PYTHONUTF8='1'
python -c "from lib.checkpoint import init_project; print(init_project('late-ring-live-action-mv', title='迟到的戒指', pipeline_type='cinematic'))"
```

Expected: project directory and `project.json` exist under `projects/late-ring-live-action-mv/`.

- [ ] **Step 3: Write exact approved preproduction artifacts**

Use `apply_patch` to create the five JSON artifacts. Required values include:

```json
{
  "project_id": "late-ring-live-action-mv",
  "pipeline": "cinematic",
  "selected_concept": "c1-late-ring",
  "target_duration_seconds": 70,
  "target_platform": "tiktok",
  "aspect_ratio": "9:16",
  "renderer_family": "cinematic-trailer",
  "render_runtime": "remotion",
  "composition_mode": "atelier",
  "video_provider": "google_flow_mcp_video",
  "music_provider": "google_flow_mcp_music",
  "approved_fallback": null
}
```

The proposal must include all three concepts presented to the user, concept A selected, a zero-dollar placeholder only where registry pricing is genuinely unavailable, and notes that subscription credits must be confirmed in the live Flow UI before each call.

- [ ] **Step 4: Validate and checkpoint research and proposal**

Run a Python command that loads the JSON artifacts and calls `write_checkpoint(..., pipeline_type='cinematic')`. Research writes `status='completed'`. Proposal writes `status='completed'` with `human_approved=True`, because the user explicitly selected concept A, approved the provider/runtime plan, reviewed the written spec, and said to begin execution.

Expected: `checkpoint_research.json` and `checkpoint_proposal.json` exist and schema validation passes.

- [ ] **Step 5: Verify project state without Git mutation**

Run:

```powershell
python -c "from lib.checkpoint import get_next_stage; print(get_next_stage(None, 'late-ring-live-action-mv'))"
```

Expected: `script` or the next uncompleted cinematic stage. Do not commit.

### Task 2: Materialize the Approved Script and Scene Plan

**Files:**
- Create: `projects/late-ring-live-action-mv/artifacts/script.json`
- Create: `projects/late-ring-live-action-mv/artifacts/scene_plan.json`
- Create: `projects/late-ring-live-action-mv/artifacts/character_consistency.json`
- Create: `projects/late-ring-live-action-mv/artifacts/still_generation_plan.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_script.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_scene_plan.json`

**Interfaces:**
- Consumes: selected proposal, approved dialogue/lyrics, eight-source timing, and continuity rules.
- Produces: exact prompts and asset dependencies for Codex still generation.

- [ ] **Step 1: Create `script.json` with exact timing**

Use sections `doorway-dialogue` (0–16), `ring-drop-music-entry` (16–20), `verse-one` (20–30), `verse-two` (30–42), `chorus` (42–58), and `hospital-outro` (58–70). Copy the approved dialogue and revised non-spoiler lyrics verbatim. Record the ring impact as the music trigger, silence windows, measured female-vocal delivery, and no explanatory diagnosis before the hospital reveal.

- [ ] **Step 2: Validate and checkpoint the script**

Load `script.json` and call `write_checkpoint` for stage `script`, `status='completed'`, `human_approved=True`, and `pipeline_type='cinematic'`. The approval evidence is the user's explicit acceptance of the dialogue and lyrics section.

Expected: schema validation passes and `checkpoint_script.json` exists.

- [ ] **Step 3: Create `scene_plan.json` with eight exact source scenes**

The selected final intervals must be `[0,10]`, `[10,20]`, `[20,30]`, `[30,40]`, `[40,50]`, `[50,60]`, `[60,66]`, and `[66,70]`. Source units 07 and 08 are each generated as ten-second clips, with only 6 and 4 seconds respectively selected in Remotion. Each scene must explicitly contain:

```json
{
  "type": "generated",
  "shot_intent": "why the shot exists",
  "narrative_role": "emotional_beat",
  "information_role": "what the viewer learns or feels",
  "shot_language": {
    "shot_size": "medium",
    "camera_movement": "static",
    "lens_mm": 85,
    "lighting_key": "natural",
    "depth_of_field": "shallow",
    "color_temperature": "neutral"
  },
  "character_actions": [],
  "texture_keywords": ["photoreal live action", "subtle black diffusion"],
  "required_assets": []
}
```

Use `metadata.five_aspect_contracts` for Subject, Subject Motion, Scene/Overlays, Spatial Framing, and Camera when the base schema has no dedicated field. Mark overlays as `N/A` except restrained subtitles added in Remotion.

- [ ] **Step 4: Create identity and still dependency contracts**

`character_consistency.json` must lock face, age, hair, wardrobe, height ratio, doorway axis, ring box, loose ring, scene color, and forbidden changes. `still_generation_plan.json` must list thirteen deliverables in dependency order: character sheets first, shared-scale and doorway anchors second, the ring-drop/cup match pair, happy-memory anchors, sofa/white-blanket continuity, hospital/empty-chair reveal, and final doorway ring-pickup anchor last.

- [ ] **Step 5: Validate and checkpoint the scene plan**

Call `write_checkpoint` for `scene_plan`, `status='completed'`, `human_approved=True`, and `pipeline_type='cinematic'`. The approval evidence is the user's explicit acceptance of the eight-source design, continuity plan, photoreal requirement, Remotion runtime, black-diffusion treatment, and the split hospital/ring-pickup ending.

Expected: `checkpoint_scene_plan.json` exists and `get_next_stage` returns `assets`.

### Task 3: Generate and Review the Thirteen Photoreal Still Deliverables

**Files:**
- Create: `projects/late-ring-live-action-mv/assets/stills/characters/*.png`
- Create: `projects/late-ring-live-action-mv/assets/stills/scenes/*.png`
- Modify: `projects/late-ring-live-action-mv/checkpoint_assets.json`

**Interfaces:**
- Consumes: `character_consistency.json`, `still_generation_plan.json`, and `scene_plan.json`.
- Produces: approved identity and scene anchors for every Google Flow call.

- [ ] **Step 1: Read required image-generation guidance**

Read the installed `imagegen` skill completely. Do not call image generation until its reference and edit instructions are understood.

- [ ] **Step 2: Mark assets stage in progress**

Write an `in_progress` assets checkpoint with `metadata.partial_progress.completed_still_ids=[]` and zero spend.

- [ ] **Step 3: Generate female and male character sheets**

Use Codex image generation for photoreal live-action casting sheets. Generate no celebrity likeness. Review face identity, hands, skin, age, hair, and wardrobe before accepting each file.

- [ ] **Step 4: Generate shared-scale and doorway anchors**

Reference both approved character sheets. Generate shared height/wardrobe reference, doorway spatial anchor, unit 01 start, unit 01 end/unit 02 start, and unit 02 end with the departing female in the background plus a macro spinning ring in the foreground.

- [ ] **Step 5: Generate happy-memory, ring, and hospital anchors**

Reference the approved character sheets and relevant prior scene anchors. Generate the kitchen start frame with a top-down circular cup rim matching the spinning ring, then happy kitchen, happy rain, happy living-room/photo, happy sofa with the woman asleep under a white blanket and waking with a smile, cold hospital/empty-chair reveal, and final doorway ring-pickup frames. Do not show illness clues before unit 07.

- [ ] **Step 6: Update partial checkpoint after every accepted still**

Record asset id, absolute and project-relative path, model receipt or response id when available, prompt-contract version, status, and review notes. Never record secrets.

- [ ] **Step 7: Present the thirteen stills and stop at the still-review gate**

Show the filmstrip grouped by characters, doorway continuity, ring transition, happy memories, return to reality, and hospital reveal. Report zero Google Flow calls so far. Do not call Google Flow until the user approves the stills.

### Task 4: Generate the Original Song and the Two-Unit Sample

**Files:**
- Create: `projects/late-ring-live-action-mv/assets/music/late-ring-song.*`
- Create: `projects/late-ring-live-action-mv/assets/music/receipt.json`
- Create: `projects/late-ring-live-action-mv/assets/video/unit-01.*`
- Create: `projects/late-ring-live-action-mv/assets/video/unit-02.*`
- Create: `projects/late-ring-live-action-mv/assets/video/unit-01-receipt.json`
- Create: `projects/late-ring-live-action-mv/assets/video/unit-02-receipt.json`
- Create: `projects/late-ring-live-action-mv/assets/sample/sample_v1.mp4`
- Modify: `projects/late-ring-live-action-mv/checkpoint_assets.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_sample.json`

**Interfaces:**
- Consumes: user-approved stills, exact lyrics, doorway continuity frames, and current Flow UI identity/model/credit evidence.
- Produces: full song plus a 20-second sample proving cast, dialogue, motion, continuity, and music entry.

- [ ] **Step 1: Read provider Layer 2 and Layer 3 skills**

Read the current tool info for `google_flow_mcp_music` and `google_flow_mcp_video`, then read all listed `agent_skills`: `music`, `lyria`, `gemini-omni`, and `ai-video-gen`.

- [ ] **Step 2: Re-run provider preflight and present the music call**

Verify the exact Flow project identity, available model/variant, and displayed credit cost. Announce `google_flow_mcp_music`, Google Flow, the visible music model, full-song purpose, and sample status. Stop if the visible identity/model differs or new credits are not approved.

- [ ] **Step 3: Generate and validate the full song**

Generate approximately 70 seconds with the approved Chinese lyrics, young female vocal, 72 BPM, felt piano, restrained cello/strings, controlled chorus, and sparse hospital outro. Validate duration, readable Mandarin, lyric order, no imitation of a named singer, and no unapproved style change.

- [ ] **Step 4: Present and run video unit 01**

Announce the exact Flow video model and displayed credits. Bind female/male sheets, doorway anchor, unit 01 start, and unit 01 end. Generate one ten-second live-action clip with no axis change.

- [ ] **Step 5: Present and run video unit 02**

Extract unit 01 final frame, bind it as unit 02 start, and retain the same cast, wardrobe, door state, light direction, eyelines, ring box, and loose ring. Generate one ten-second clip containing the breakup, reaction, departure, physically plausible ring drop, and a readable macro moment of the ring rotating on the floor.

- [ ] **Step 6: Build and validate `sample_v1.mp4`**

Use the approved Remotion runtime or a deterministic sample composition. Preserve doorway ambience and dialogue, align the ring's metal impact around 17–18 seconds with the music's first piano attack, and hold the spinning-ring macro long enough to motivate unit 03. Validate 9:16, approximately 20 seconds, and audio intelligibility with ffprobe and frame review.

- [ ] **Step 7: Write sample checkpoint and stop**

Record actual credits, tools, provider/model variants, files, and review findings. Set `checkpoint_sample.json` to `awaiting_human`. Present the playable sample and stop for approval.

### Task 5: Generate Units 03–08 and Complete the Asset Gate

**Files:**
- Create: `projects/late-ring-live-action-mv/assets/video/unit-03.*` through `unit-08.*`
- Create: `projects/late-ring-live-action-mv/assets/video/unit-03-receipt.json` through `unit-08-receipt.json`
- Create: `projects/late-ring-live-action-mv/artifacts/asset_manifest.json`
- Modify: `projects/late-ring-live-action-mv/checkpoint_assets.json`

**Interfaces:**
- Consumes: approved sample, song, stills, transition boundary table, and current Flow credits.
- Produces: all motion and audio assets needed by edit and compose.

- [ ] **Step 1: Mark sample approved and resume assets**

Rewrite sample checkpoint with `status='completed'` and `human_approved=True`. Read assets partial progress; do not regenerate completed units.

- [ ] **Step 2: Generate units 03–08 one at a time**

Before each call, announce tool/provider/model, batch status, purpose, and displayed credits. Use approved references and boundary pairs: spinning ring→top-down cup rim, kitchen water→rain, closing umbrella→living-room photo, happy photo→happy sofa, sofa white blanket→hospital bed, and hospital empty chair→doorway floor/ring pickup. Units 03–06 must contain only happy memories and no illness clue.

- [ ] **Step 3: Review and checkpoint after every unit**

Check identity, wardrobe, hands, props, camera axis, motion, black diffusion, color progression, ten-second duration, and boundary usability. On failure, stop and request a bounded retry; do not spend the next call.

- [ ] **Step 4: Build and validate the complete asset manifest**

Include all approved images, eight source videos, song, ambience/SFX, subtitles, provider/model receipts, durations, resolutions, selected in/out points, and actual reported cost or subscription-credit notes.

- [ ] **Step 5: Present the full filmstrip and stop at assets gate**

Write assets checkpoint as `awaiting_human`. Show every scene asset, cumulative credits, and projected local compose cost. Do not render the final composition before approval.

### Task 6: Author the Remotion Atelier Composition and Edit Contract

**Files:**
- Create: `projects/late-ring-live-action-mv/artifacts/edit_decisions.json`
- Create: `projects/late-ring-live-action-mv/remotion/index.tsx`
- Create: `projects/late-ring-live-action-mv/remotion/LiveActionBreakupMV.tsx`
- Create: `projects/late-ring-live-action-mv/remotion/continuity.ts`
- Create: `projects/late-ring-live-action-mv/checkpoint_edit.json`

**Interfaces:**
- Consumes: approved asset manifest and eight exact selected scene intervals.
- Produces: deterministic 1080×1920, 24fps composition and schema-valid edit decisions.

- [ ] **Step 1: Read Remotion guidance**

Read the current cinematic edit and compose directors, bespoke-composition skill, and `remotion-best-practices`/`remotion` Layer 3 skills before authoring TypeScript.

- [ ] **Step 2: Write the failing validation first**

Create a project-local validation that asserts eight unique scene ids, selected durations `[10,10,10,10,10,10,6,4]`, contiguous timeline coverage from 0 to 70 seconds, 1080×1920 output, 24fps, exact asset existence, and `render_runtime='remotion'`.

- [ ] **Step 3: Run validation and observe failure**

Expected: FAIL because composition and edit decisions do not yet exist.

- [ ] **Step 4: Implement the minimal atelier composition**

Use `<OffthreadVideo>` for each approved unit, a single continuous music track, restrained dialogue subtitles, hard/match cuts, one fade-to-black ending, and no decorative motion graphics. Apply the approved color and diffusion progression without blurring eyes or props.

- [ ] **Step 5: Write `edit_decisions.json`**

Record exact in/out points, audio levels, the ring-impact music trigger at approximately 17–18 seconds, ring-to-cup match cut, remaining match-cut boundaries, subtitle timing, grade targets, `renderer_family='cinematic-trailer'`, and `render_runtime='remotion'`.

- [ ] **Step 6: Run validation and type checks**

Expected: all timeline, asset, runtime, TypeScript, and Remotion composition checks pass.

- [ ] **Step 7: Complete edit checkpoint**

Write `checkpoint_edit.json` with schema-valid edit decisions and review findings. Do not commit.

### Task 7: Render, Inspect, and Present the Final Master

**Files:**
- Create: `projects/late-ring-live-action-mv/renders/final.mp4`
- Create: `projects/late-ring-live-action-mv/artifacts/render_report.json`
- Create: `projects/late-ring-live-action-mv/artifacts/final_review.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_compose.json`
- Create: `projects/late-ring-live-action-mv/checkpoint_publish.json`

**Interfaces:**
- Consumes: approved assets and validated Remotion composition.
- Produces: playable final video and acceptance evidence; no external publication.

- [ ] **Step 1: Render the Remotion master**

Render 1080×1920 at 24fps with H.264 video and AAC audio. Store only under the run-owned render path.

- [ ] **Step 2: Probe the rendered file**

Run ffprobe and require positive duration near 70 seconds, 1080×1920 resolution, video and audio streams, and decodable media.

- [ ] **Step 3: Perform visual and audio review**

Sample frames from every scene and both sides of every boundary. Verify cast identity, hands/props, eyelines, black-diffusion progression, cold hospital landing, subtitle safety, intelligible dialogue, lyric order, and music balance.

- [ ] **Step 4: Write render and final-review artifacts**

Record exact runtime used, no runtime swap, ffprobe evidence, review findings, unresolved risks, and actual provider receipts.

- [ ] **Step 5: Present final master at compose gate**

Write compose checkpoint as `awaiting_human`, show the playable file, actual credits, and acceptance summary, then stop.

- [ ] **Step 6: Package locally after approval**

After user approval, mark compose completed and create a local export package plus `publish_log` with `draft_only/local_export` status. Do not upload or publish.

## Plan Self-Review Record

- Spec coverage: every approved requirement maps to Tasks 1–7.
- Placeholder scan: no TBD, TODO, or undefined implementation placeholder is permitted.
- Interface consistency: project id, eight source unit ids, `[10,10,10,10,10,10,6,4]` selected timeline, providers, Remotion runtime, and asset paths are identical across tasks.
- Safety: Google Flow calls remain behind live identity/model/credit announcements; provider switching, static fallback, external publication, Git commit, and push remain unauthorized.
