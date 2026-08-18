# One Prompt to Final Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and locally verify a 55-second, 1920x1080 Chinese animated explainer titled “一句话如何变成一条完整视频”, using the approved Grok media/TTS path, Codex built-in image generation, Pixabay music, and Remotion composition.

**Architecture:** Run the repository's `animated-explainer` pipeline in one canonical project workspace. Each stage writes a schema-valid artifact and checkpoint before the next stage begins. Generated media stays under `projects/one-prompt-to-final-video/`; no core template or provider code changes are expected. The final deliverable is composed with Remotion's stock `Explainer` composition in `templated` authoring mode and is accepted only after media probing, full decode, and visual/audio review.

**Tech Stack:** OpenMontage checkpoint/artifact contracts, Grok CLI OAuth providers, Codex `imagegen`, Pixabay music search, Remotion 4.0.484, FFmpeg/ffprobe, Python 3, JSON Schema.

## Global Constraints

- Work only in `E:\project\OpenMontage` and `projects/one-prompt-to-final-video/`.
- Use one main owner; do not spawn subagents unless the user explicitly authorizes them.
- Do not push, publish, upload, deploy, or create a vertical variant.
- Do not change provider, model family, runtime, authoring mode, narration, or music plan without explicit user approval and an appended `decision_log` entry.
- Announce exact tool, provider, provider variant, purpose, and sample/batch status before every paid or consequential generation call.
- Do not silently fall back. If Grok, Codex image generation, Pixabay, or Remotion fails, stop at that boundary and report the failure and options.
- Keep all generated files inside the canonical project workspace and pass explicit output paths.
- Follow every `human_approval_default: true` gate. An approval for one stage does not approve a later stage.
- Validate every canonical artifact against `schemas/artifacts/` before checkpointing.
- Preserve unrelated worktree changes. Local commits are allowed; remote Git actions are not.

---

### Task 1: Re-establish preflight and initialize the canonical project

**Files:**

- Create: `projects/one-prompt-to-final-video/project.json`
- Create: `projects/one-prompt-to-final-video/artifacts/`
- Create: `projects/one-prompt-to-final-video/assets/{images,video,audio,music}/`
- Create: `projects/one-prompt-to-final-video/renders/`

- [ ] Read the executive producer, research director, reviewer, and checkpoint protocol instructions in full.

```powershell
Get-Content -Raw skills/pipelines/explainer/executive-producer.md
Get-Content -Raw skills/pipelines/explainer/research-director.md
Get-Content -Raw skills/meta/reviewer.md
Get-Content -Raw skills/meta/checkpoint-protocol.md
```

Expected: all four files are readable; no production command has run yet.

- [ ] Re-run the human-readable provider preflight and record its output for this run.

```powershell
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), ensure_ascii=False, indent=2))"
```

Expected: Grok is available for video generation and TTS; FFmpeg, Remotion, and HyperFrames are available; the image registry limitation and Codex interactive image path are stated explicitly; any live warning is surfaced rather than hidden.

- [ ] Initialize the project exactly once and open its Backlot board.

```powershell
python -c "from lib.checkpoint import init_project; print(init_project('one-prompt-to-final-video', title='一句话如何变成一条完整视频', pipeline_type='animated-explainer'))"
python -m backlot open one-prompt-to-final-video
```

Expected: `project.json` and the canonical folders exist. Backlot opening is best-effort and is not a production blocker.

- [ ] Verify the workspace marker and next stage.

```powershell
python -c "from pathlib import Path; from lib.checkpoint import get_next_stage; print(get_next_stage(Path('projects'), 'one-prompt-to-final-video', 'animated-explainer'))"
```

Expected: the next stage is `research`.

### Task 2: Produce and checkpoint the research brief

**Files:**

- Create: `projects/one-prompt-to-final-video/artifacts/research_brief.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_research.json`

- [ ] Write an `in_progress` research checkpoint before research begins.
- [ ] Research the current OpenMontage repository and at least five primary/local authoritative sources relevant to agent-driven video production, Remotion composition, Grok-generated media, and review gates. Record exact URLs or local repository paths; do not invent citations.
- [ ] Build three genuinely distinct narrative angles. The recommended angle must explain the path `prompt -> research/script -> assets -> timeline -> QC -> final.mp4` to a technically curious Chinese audience.
- [ ] Include at least three concrete sourced data points and real audience questions.
- [ ] Save the canonical JSON and validate it.

```powershell
python -c "import json; from pathlib import Path; from schemas.artifacts import validate_artifact; p=Path('projects/one-prompt-to-final-video/artifacts/research_brief.json'); d=json.loads(p.read_text(encoding='utf-8')); validate_artifact('research_brief', d); print(p)"
```

Expected: validation exits 0.

- [ ] Run the stage self-review, fix critical findings, and checkpoint `research` as `completed` with the artifact attached.

### Task 3: Materialize the already approved proposal decisions

**Files:**

- Create: `projects/one-prompt-to-final-video/artifacts/proposal_packet.json`
- Create: `projects/one-prompt-to-final-video/artifacts/decision_log.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_proposal.json`

- [ ] Read `skills/pipelines/explainer/proposal-director.md` in full before drafting.
- [ ] Produce three differentiated concepts grounded in the research and select “一句话如何变成一条完整视频”.
- [ ] Record the approved delivery contract:

```text
Format: 55 seconds, 16:9, 1920x1080, Chinese narration
Runtime: Remotion 4.0.484
Runtime alternatives considered: Remotion, HyperFrames, FFmpeg
Authoring mode: templated
Composition: Explainer
Visual path: two Codex images plus two Grok clips plus Remotion motion graphics
Voice: Grok TTS, Chinese, ara voice
Music: Pixabay royalty-free search/download, subject to the selected asset's license metadata
No fallback, no publishing, no vertical variant
```

- [ ] Itemize costs using live tool estimates. For subscription-backed Grok/Codex calls whose per-call dollar cost is not exposed, label them `subscription quota / unpriced`; do not invent a price.
- [ ] Append decision records for concept, provider selection, voice selection, music source, `render_runtime_selection`, `composition_mode`, output format, and approval policy. Runtime options must include both Remotion and HyperFrames and explain why Remotion was selected for this brief.
- [ ] Set proposal approval to the user's confirmed status and include the current conversation approval as evidence.
- [ ] Validate both artifacts.

```powershell
python -c "import json; from pathlib import Path; from schemas.artifacts import validate_artifact; root=Path('projects/one-prompt-to-final-video/artifacts'); [(validate_artifact(n, json.loads((root/f'{n}.json').read_text(encoding='utf-8'))), print(n)) for n in ('proposal_packet','decision_log')]"
```

Expected: both artifact names print and the command exits 0.

- [ ] Self-review and write the gated proposal checkpoint as `completed` with `human_approved=True`; do not ask the user to approve the same proposal twice unless the artifact materially differs from the approved design.

### Task 4: Write the timed narration script

**Files:**

- Create: `projects/one-prompt-to-final-video/artifacts/script.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_script.json`

- [ ] Read `skills/pipelines/explainer/script-director.md` and `skills/meta/voice-performance-director.md` in full.
- [ ] Write the script to this exact beat structure:

```text
00-04  Hook: 一句话，不是直接变成视频。
04-10  Research/terminal: first turn the idea into a verifiable brief.
10-17  Pipeline/progress: script, scenes, assets, edit, compose.
17-25  Comparison: model creativity versus deterministic code.
25-34  Grok motion: generated motion supplies visual energy.
34-43  Backlot: artifacts/checkpoints make decisions inspectable.
43-50  QC/KPI: duration, decoding, image, and audio checks.
50-55  Landing: one prompt becomes a controlled production chain.
```

- [ ] Keep spoken Chinese within the director's duration/word-count tolerance. Add concrete pacing, pause, emphasis, and pronunciation directions for the `ara` voice, with enhancement cues every 8-10 seconds.
- [ ] Validate the script artifact.

```powershell
python -c "import json; from pathlib import Path; from schemas.artifacts import validate_artifact; p=Path('projects/one-prompt-to-final-video/artifacts/script.json'); validate_artifact('script', json.loads(p.read_text(encoding='utf-8'))); print(p)"
```

Expected: validation exits 0 and total scripted duration is within 10% of 55 seconds.

- [ ] Self-review and write `checkpoint_script.json` as `awaiting_human`; present the narration text and performance plan, then end the turn for explicit approval.

### Task 5: Build the scene plan after script approval

**Files:**

- Create: `projects/one-prompt-to-final-video/artifacts/scene_plan.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_scene_plan.json`

- [ ] After explicit script approval, mark the script checkpoint completed with `human_approved=True`.
- [ ] Read `skills/pipelines/explainer/scene-director.md` in full.
- [ ] Translate the approved script into these non-overlapping scenes:

```text
S01 00-04 hero_title
S02 04-10 terminal_scene
S03 10-17 progress_bar
S04 17-25 comparison
S05 25-34 Grok clip with provider_chip overlay
S06 34-43 screenshot_scene showing the local Backlot board
S07 43-50 kpi_grid with stat_reveal overlay
S08 50-55 hero_title closing card
```

- [ ] Assign every non-procedural asset an explicit output path under the project workspace. Cover the full 55 seconds with no gaps or overlaps and use at least three scene types.
- [ ] Validate, self-review, and write the scene-plan checkpoint as `awaiting_human`; present the timeline and asset list, then end the turn for explicit approval.

### Task 6: Approve a Grok voice sample before full narration

**Files:**

- Create: `projects/one-prompt-to-final-video/assets/audio/voice-sample-ara.mp3`
- Update: `projects/one-prompt-to-final-video/artifacts/decision_log.json`

- [ ] After explicit scene-plan approval, mark the scene checkpoint completed with `human_approved=True`.
- [ ] Read the asset director and the Grok CLI TTS Layer 3 skill in full.

```powershell
Get-Content -Raw skills/pipelines/explainer/asset-director.md
Get-Content -Raw .agents/skills/grok-cli-tts/SKILL.md
```

- [ ] Announce the exact paid/consequential call: `grok_cli_tts`, Grok subscription/OAuth, `ara` Chinese voice, voice sample only.
- [ ] Generate one 8-12 second excerpt from the approved opening lines through the registered tool path, writing exactly to `voice-sample-ara.mp3`.
- [ ] Probe and fully decode the sample.

```powershell
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,sample_rate,channels -of json projects/one-prompt-to-final-video/assets/audio/voice-sample-ara.mp3
ffmpeg -v error -i projects/one-prompt-to-final-video/assets/audio/voice-sample-ara.mp3 -f null NUL
```

Expected: valid MP3, audible Chinese speech, no decode errors.

- [ ] Present the sample to the user and end the turn. Do not generate the full narration until the sample is explicitly approved.

### Task 7: Generate and review all production assets

**Files:**

- Create: `projects/one-prompt-to-final-video/assets/images/prompt-orchestration.png`
- Create: `projects/one-prompt-to-final-video/assets/images/quality-gates.png`
- Create: `projects/one-prompt-to-final-video/assets/video/grok-creative-motion.mp4`
- Create: `projects/one-prompt-to-final-video/assets/video/grok-controlled-output.mp4`
- Create: `projects/one-prompt-to-final-video/assets/audio/narration-ara.mp3`
- Create: `projects/one-prompt-to-final-video/assets/music/background.mp3`
- Create: `projects/one-prompt-to-final-video/assets/subtitles.srt`
- Create: `projects/one-prompt-to-final-video/artifacts/asset_manifest.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_assets.json`

- [ ] Append the approved voice sample decision to `decision_log` using the same `(category, subject)` pair as the original voice choice.
- [ ] Read each selected tool's declared Layer 3 skills before its first production call: Codex `imagegen`, Grok media, Grok TTS, music/media use, and FFmpeg as applicable.
- [ ] Announce and make two separate Codex built-in image generation calls. Generate text-free 16:9 supporting visuals with a consistent dark graphite, electric cyan, and warm amber palette. Save them to the exact image paths above.
- [ ] Inspect both images visually before continuing; reject unreadable UI-like text, accidental logos, and inconsistent style.
- [ ] Announce and make two separate Grok subscription video calls through `grok_cli_video`. Use 16:9, approximately 6-8 seconds each, with restrained camera motion and no embedded typography. Save to the exact video paths above.
- [ ] Probe, fully decode, and sample frames from both clips. Reject semantic drift such as turning software-flow metaphors into aircraft or unrelated objects.
- [ ] Announce and generate the full approved narration through `grok_cli_tts` with the approved `ara` sample settings.
- [ ] Search Pixabay for a low-intensity technology/ambient track, preserve source URL and license metadata, download one approved-length track, and save it as `background.mp3`. If Pixabay is unavailable or licensing metadata is insufficient, stop and ask rather than substituting another source.
- [ ] Generate timed SRT subtitles from the approved script and narration timing.
- [ ] Build `asset_manifest.json` with provenance, provider/model/variant, prompt, seed when available, output path, duration/dimensions, source URL/license for music, and scene linkage.
- [ ] Validate every path and the manifest.

```powershell
python -c "import json; from pathlib import Path; from schemas.artifacts import validate_artifact; p=Path('projects/one-prompt-to-final-video/artifacts/asset_manifest.json'); d=json.loads(p.read_text(encoding='utf-8')); validate_artifact('asset_manifest', d); missing=[x.get('path') for x in d.get('assets',[]) if x.get('path') and not Path(x['path']).exists()]; assert not missing, missing; print(p)"
```

Expected: schema-valid manifest and no missing files.

- [ ] Create a contact sheet/frame review, self-review scene by scene, and write `checkpoint_assets.json` as `awaiting_human`; present the assets and current cost/quota snapshot, then end the turn for explicit approval.

### Task 8: Author the edit decisions and Remotion props

**Files:**

- Create: `projects/one-prompt-to-final-video/artifacts/edit_decisions.json`
- Create: `projects/one-prompt-to-final-video/artifacts/remotion-props.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_edit.json`

- [ ] After explicit asset approval, mark the asset checkpoint completed with `human_approved=True`.
- [ ] Read `skills/pipelines/explainer/edit-director.md`, `.agents/skills/remotion/SKILL.md`, and `.agents/skills/remotion-best-practices/SKILL.md` in full.
- [ ] Build the 55-second timeline with exact cuts, overlays, subtitles, narration, background music, fades, and ducking. Use only existing stock scene types and props; do not modify Remotion source code or introduce a new template.
- [ ] Set `render_runtime: remotion`, `composition_mode: templated`, `composition_id: Explainer`, 1920x1080, and the repository's supported frame rate.
- [ ] Validate all asset references, full timeline coverage, no gaps/overlaps, subtitle safe areas, narration intelligibility, and music ducking.
- [ ] Validate `edit_decisions.json`, self-review it, and checkpoint `edit` as `completed`.

### Task 9: Render and perform final media QC

**Files:**

- Create: `projects/one-prompt-to-final-video/renders/final.mp4`
- Create: `projects/one-prompt-to-final-video/artifacts/render_report.json`
- Create: `projects/one-prompt-to-final-video/artifacts/final_review.json`
- Create: `projects/one-prompt-to-final-video/checkpoint_compose.json`

- [ ] Read `skills/pipelines/explainer/compose-director.md` in full.
- [ ] Verify the installed local runtime resolves to Remotion 4.0.484 and that composition enumeration still includes `Explainer`.

```powershell
Set-Location remotion-composer
npx.cmd remotion compositions src/index.tsx
Set-Location ..
```

Expected: `Explainer` appears at 1920x1080 and no runtime-not-found error occurs.

- [ ] Render through the registered `video_compose` tool with explicit input props and output path; do not invoke an alternate runtime after failure.
- [ ] Probe the final file and fully decode both streams.

```powershell
ffprobe -v error -show_entries format=duration,size:stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels -of json projects/one-prompt-to-final-video/renders/final.mp4
ffmpeg -v error -i projects/one-prompt-to-final-video/renders/final.mp4 -map 0:v:0 -map 0:a:0 -f null NUL
```

Expected: playable MP4; H.264 video at 1920x1080; an audio stream; duration within 52.25-57.75 seconds; zero decode errors.

- [ ] Sample frames from the opening, each scene boundary, and closing. Verify no black/blank frames, clipped text, placeholder assets, broken fonts, accidental watermarks, or timing discontinuities.
- [ ] Listen to the opening, a middle transition, and the ending. Verify clear narration, correct pronunciation, no clipping, music ducking, and clean fade-out.
- [ ] Write and validate `render_report.json` and `final_review.json`, including exact probe results and any non-blocking warnings.
- [ ] Checkpoint `compose` as `completed` only when the final MP4 and both artifacts pass.

### Task 10: Hand off the local deliverable

**Files:**

- Verify: `projects/one-prompt-to-final-video/renders/final.mp4`
- Verify: `projects/one-prompt-to-final-video/artifacts/render_report.json`
- Verify: `projects/one-prompt-to-final-video/artifacts/final_review.json`

- [ ] Re-read Git status and confirm generated project assets remain ignored and no unrelated files changed.
- [ ] Run the smallest relevant contract tests only if production required source changes; otherwise state that no source code changed during the run.
- [ ] Present the final video as an absolute clickable/renderable local path together with duration, resolution, codecs, validation outcome, and known limitations.
- [ ] Stop before the `publish` stage. Do not push commits or upload/publish the video.

## Completion Evidence

- `projects/one-prompt-to-final-video/renders/final.mp4` exists and is playable.
- Duration is within 5% of 55 seconds, resolution is 1920x1080, video is H.264, and audio is present.
- Full FFmpeg decode succeeds with no errors.
- `research_brief`, `proposal_packet`, `decision_log`, `script`, `scene_plan`, `asset_manifest`, `edit_decisions`, `render_report`, and `final_review` are schema-valid.
- All required gated checkpoints contain explicit human approval.
- No unapproved provider/runtime fallback, publication, upload, push, or unrelated repository mutation occurred.
