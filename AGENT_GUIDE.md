# OpenMontage - Agent Guide

## Project-owned generation route

OpenMontage owns provider discovery, project state, generation, budgets and
acceptance, regardless of whether the request arrives from Feishu or a local
Codex session. The global `ai-video-gen` entrypoint only points here; it must
not duplicate these rules. Feishu Bridge owns task intake and result delivery,
not video production or provider configuration.

Shared selectors default to `auto`: inspect available providers, exact model
contracts and session-native capabilities before choosing a production route.
Personal preferences belong in ignored `config.local.yaml`; shared `config.yaml`
contains portable defaults. Request-level tool, host, model and allowed-provider
constraints take precedence; `preferred_provider` is a ranking hint, not a
spending authorization or hard provider constraint. A configured preference is a selection hint;
`restrict_to_preferences: true` limits omitted-route requests to that personal
provider. Disabled providers remain optional installed integrations and are
excluded from selection. Do not change providers after a failed submission.

The executing agent owns suitability, model selection, voice performance and
creative acceptance. Code owns capability discovery, parameter validation,
transport, media integrity and receipts. Provider scoring is advisory evidence,
not a substitute for the agent's production plan. Freeze the selected tool,
host, model and authorized spending scope before generation.

When writing artifacts on Windows, save Python scripts containing non-ASCII text
as UTF-8 files and run those files. If passing a PowerShell here-string to Python
through a pipe, set `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)`
and `$env:PYTHONUTF8 = '1'` before the pipe. `PYTHONUTF8` alone does not control
PowerShell's pipe encoding. Write JSON with `encoding="utf-8"`.

Codex native `image_gen` is an optional explicit route. Check its availability
in the actual session, then register the image and provenance in the project.
Its desktop availability does not imply Worker access. Python API providers
remain usable without a Codex-native tool.

For Agnes, query `video_selector(operation="discover_models",
preferred_provider="agnes")` using the configured account before a new
production. Listing is a candidate, not proof of access; inspect applicable
plan evidence and task receipts. The agent passes the exact selected `model`.
Use the current model's contract, reuse applicable access evidence, and use the
first authorized production shot to confirm the route rather than submitting
extra test generations. Recovery retains the original task/model identity.
Selection within an already-authorized plan needs no repeated model-version
approval; another provider or spending outside that authorization still does.

For Google Flow, use `google_flow_mcp_video` through the configured local MCP
bridge and authenticated browser subscription. `google_flow` configuration
supplies the UI model and homepage. Credit ceilings default to `null` (no cap);
only use a numeric ceiling when the user explicitly requests one. A video
generation request authorizes its normal subscription-credit use: give one
brief cost notice when useful, then continue without a separate fee approval
or repeated reminders. Set `confirm_paid_generation=true` for that authorized
request; this is the transport's single-use authorization, not another user gate.
Resolve the actual model once from the approved selection or configured default,
then reuse it for subsequent shots. Keep the exact model in tool parameters and
receipts; do not repeat its name or request another model confirmation in routine
progress updates. Discuss the model again only if that selection changes or a
model-specific limitation affects the result. The adapter exits Agent mode when
necessary and verifies ordinary video settings (4/6/8/10 seconds,
16:9 or 9:16, 720p, one result), then types without submitting and requires
acknowledgement after the separate generation click. An existing output-owned
`.flow-attempt.json` requires reconciliation, never another submission.
Run Flow shots sequentially against its shared browser profile.
After submission, query `flow_generation_status` with the returned generation
identity. Persist observations in the attempt record and status timeline;
report only observed queue/processing/terminal states and provider progress.
Preparation before the generation click is explicitly `not_started`; a fresh
MCP session's no-submission state describes that session, not a historical
provider task. Submission invoked without evidence remains `unknown`.
After an MCP restart, pass the saved generation identity, provider `job_id` and
original project URL to `flow_generation_status`; it reads that named provider
record and never submits again. Flow native `scheduled`/`pending` means
`queued` (waiting/processing); its interface does not expose a reliable separate
running phase or percentage. Report the provider label alongside the state.
Missing evidence or an observation timeout means status unknown, not failure
or permission to resubmit. Provider success still requires downloading and
validating the actual video before delivery.
Use the bridge's unified `flow_upload` for all platform-supported materials,
including file-input and native media-picker surfaces. User-authorized reference
files may acknowledge the upload-rights notice for that action. The adapter
requires a verified completed upload/association before typing or submitting;
an uploading placeholder is not a usable reference.

For Omni generation and conversational-edit prompting across different use
cases, consult `docs/references/google-omni-video-prompting.md`. It summarizes
the official guide, separates Flow capabilities from older API preview
limitations, and offers adaptable examples. It is a creative reference, not
an additional preflight or approval step; keep the selected model and route.
The user-callable `$omni-video-director` skill coordinates story, references,
performance, conversational edits and composition while using this project's
existing production authority and execution paths.

For Google Omni / Flow generated presenter speech, follow the project-owned
[Chinese redub workflow](docs/references/omni-chinese-redub.md). Pure Chinese
speech requires independent dubbing and phrase/pause alignment to the native
audio while preserving the picture. Pure English and mixed-language speech
keep native audio and skip redubbing, synchronization and listening-specific
checks. Classify the complete spoken script, not individual Chinese subclips
inside a mixed-language video. This user-selected language policy takes
precedence over generic presenter audio/mouth-review instructions.

Gemini has two distinct optional transports: `gemini_tts` uses the upstream
Interactions contract; `gemini_generate_content_tts` preserves the verified
project generateContent route, audio normalization and bounded recovery.
The generateContent adapter defaults to `gemini-3.8-flash-tts` using its 3.8
audio request schema. Voice remains required per production, with no default.
Explicit legacy 3.1 requests retain their original transport parameters.
Select the exact tool/model rather than treating these interfaces as equivalent.
Do not silently upgrade a production's API or voice, or call TTS again through a
composition engine's media helper.

Known transient provider failures may use the adapter's bounded same-request
recovery. Respect explicit user call limits. Authentication, invalid input and
safety blocks stop. Unknown submission outcomes retain their receipt/task
identity for reconciliation; never create a duplicate because a session ended.
Unknown plan cost stays unknown, never zero. Record actual provider/model,
attempts, media hashes and result evidence without exposing credentials.

Audio tempo and music-level thresholds are advisory by default. The model/owner
reviews the actual mix against the agreed style. `edit_decisions.audio_review_policy`
can declare project thresholds with `mode: enforce` when agreed; missing media,
corrupt output and required transcript/provenance failures remain hard checks.

### Bounded multi-shot execution path (HARD RULE)

For a production with several paid or long-running generated shots, use one
run-owned execution contract from asset preflight through final review. Freeze
the project ID, approved provider/model, provider input schema, render runtime,
cost policy, reuse set, and forbidden substitutions before the first external
submission. Account-observed capability and the user's stated subscription
are authoritative for that run; public pricing or retirement notices must not
silently replace them. Unknown plan cost or token usage stays unknown (`null`
where the owning schema permits it, otherwise omit the optional field), never
`0` or "free".

Execute the run in this order:

1. Inventory, hash, and register reusable assets once. Audit the current run's
   projections for stale provider/model/pricing claims; keep historical source
   artifacts immutable and correct only the new run-owned projection.
2. Preflight every local reference and remote reference URL before submission.
   Require a readable local file or an HTTP success with the expected media
   type and non-empty body. Reuse a proven direct URL; do not discover an image
   host failure inside a paid video call.
3. When the approved plan calls for a first-shot route check, submit exactly one
   representative shot. Decode and semantically review the actual result, then
   freeze the working provider request shape, observed output geometry, and one
   normalization policy for the remaining shots.
4. Before every submit or resubmit, inspect the persisted receipt, provider
   task ID, output path, and append-only attempt ledger. Poll or recover a
   non-terminal/unknown task with the same identity. Never create a duplicate
   merely because a process, tool cell, or conversation context disappeared.
5. After the first-shot gate passes, dispatch independent shots in a bounded
   batch only when the provider/account supports it. Use stable unique attempt
   IDs and at most 2-3 concurrent jobs; otherwise run serially. Poll every long
   job to a terminal state.
   While assets are preparing, scaffold the project-local composition once and
   build its edit against the actual final narration transcript. Keep one
   source tree for rough assembly, fine editing and accepted preview. Pending
   media may be explicit placeholders during authoring, never at acceptance.
6. Normalize and decode accepted clips as one batch, then create one aggregate
   review surface (contact sheet plus representative motion samples). Perform
   identity/action/continuity review for every shot. Regenerate only failed
   leaves with a changed request; accepted siblings remain immutable.
7. Derive manifests, cost records, and checkpoints from persisted receipts,
   hashes, media probes, and review records. Validate each artifact against its
   owning schema before checkpoint write; do not hand-copy provider facts when
   they can be projected from receipts.
8. Use the same-engine acceptance path in
   `skills/pipelines/explainer/compose-director.md`: `video_compose(preflight)`
   checks final inputs before rendering; `video_compose(preview)` renders,
   reviews and fully decodes once. The owner inspects the actual continuous
   result or its full frame sequence and records acceptance for that exact SHA.
   `video_compose(finalize)` verifies unchanged inputs and copies the accepted
   bytes into the final artifact without another render or duplicate review.
   An actual failed gate requires the smallest repair and a new preview revision.
   Raw renderer commands remain debugging surfaces, not production entries.

Within the same task, reuse already-read unchanged director skills and current
run evidence. Re-reading large guides, repeating one-off probes, or rendering
drafts solely to discover schema/entrypoint mistakes is not progress.


Start here. This is the complete operating guide and agent contract for OpenMontage.

For architecture, key files, and conventions see [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).

## First Interaction — Onboarding

When the user's first message is vague, exploratory, or asks what you can do ("make me a video", "what can you do?", "help me create something", "I want to make content"), read the onboarding skill **before** doing anything else:

**Read:** `skills/meta/onboarding.md`

This skill teaches you to run discovery, classify the user's setup, present capabilities in plain language, and offer starter prompts tailored to their available tools. The goal: get the user from "curious" to "making a video" in under 60 seconds.

**Skip onboarding** when the user arrives with a specific, actionable request (e.g., "Make a 60-second explainer about black holes"). Go directly to Rule Zero.

## Video Request Entry Point

OpenMontage is the preferred business entrypoint for natural-language video
requests, including Feishu requests that do not name a project or directory.
The executing agent interprets the requested outcome and checks current registry
capabilities; the Bridge does not classify video requests or choose providers.
Resolve project commands and relative paths against this checkout, without
changing the topic's trusted attachment identity or expanding its sandbox.

For natural-language creative intake, mixed scripts/images/footage and continued
edits in the same Feishu topic, follow the
[unified creative entry](docs/references/feishu-creative-entry.md). Interpret
the desired outcome and each material's use in the model; do not classify by
file type alone or add a business router to Bridge. Reuse known project context,
ask only for material gaps and preserve existing authorization and artifacts.

Complete-video requests retain the automatic production workflow. When the user
asks for a video plan, use the
[manual generation plan workflow](docs/references/manual-video-handoff.md).
For example, "I have a product called X; write a video plan for it" is sufficient.
Deliver Feishu plans through the project's published standalone video-plan webpage,
without the Base data-table sidebar. Keep the overview, asset and segment tables
as internal storage; their Base URLs are maintenance evidence, not user delivery
links. Verify the actual project webpage and preserve its access scope. If this
entry is unavailable, report the missing standalone entry instead of substituting
a Base link. Follow the native Base reference for the publishing/readback steps.
Users may also say "使用 ai-video-gen 技能，我有个产品叫 X，帮我写一份视频方案".
Video copy ("视频文案") is a separate text-only deliverable: write the requested
copy without generating images or videos. Naming a video skill does not turn
a copy request into a visual plan.
Plan-only requests execute the existing pipeline's pre-production stages; they
are not permission to skip Rule Zero. Select the matching existing manifest,
initialize/resume the same project, read each applicable director, and execute
research -> proposal -> script -> scene_plan -> necessary reference assets in
the manifest's order. Preserve canonical artifacts, reviews and existing
approval gates. Reuse valid prior artifacts instead of repeating stages.
Only after those inputs exist may the executor map them into the Feishu plan.
Internal stage evidence stays in the project; the final user-facing deliverable
is the standalone board. Do not generate video, audio or a composition for a
plan-only request, or mark an entire assets stage complete when only reference
images are prepared. Missing upstream evidence is an incomplete formal plan,
not a reason to invent it in a separate board JSON.
Do not require manual-generation terminology, a deliverable checklist, or a
model choice. Fill ordinary creative gaps with clearly marked suggestions;
ask only about gaps that materially affect the requested result.
Use the shared [platform-neutral visual planning flow](docs/references/visual-video-planning.md)
for both automatic production preparation and the manual handoff. It separates
reusable reference assets (identity, product, scene and style) from an optional
composed key image that fixes a segment's starting composition or interaction
state, and from the complete motion prompt. Select the least set of references
that the segment actually needs; do not require a key image, extra views or a
fixed image count when they add no control.
Organize the manual plan by generation segment: one necessary reference-image
group and one complete prompt per segment. Keep short shot/action beats inside
that prompt rather than automatically making each beat a separate generation
task; split segments when the content or explicit user requirements call for it.
Reuse the same planning and image tools. In Feishu, use the independent native
Base defined in [Feishu video-plan Base](docs/references/feishu-video-plan-base.md)
as internal storage and deliver its published standalone video-plan board as the
sole user-facing entry point. The board's
outer segment card should be a static visual preview with its title, timing,
necessary image and short summary visible by default, plus one clearly labeled
“打开操作面板” entry; it has no other expand or content-inspection control.
The opened segment detail panel must bring together actual reference images,
image use, narration/dialogue, on-screen text and one complete copyable prompt, so a user can
finish the whole segment handoff without opening the underlying asset or segment
tables. Those tables remain internal data sources maintained by the board. In a local
request, or when Word is explicitly requested, use the DOCX template; use XLSX
only when explicitly requested. Do not emit multiple formats by default.
Prepare or reuse identifiable character references for live-action, animated or
other recurring characters, product references where appearance matters, and
references for each distinct main scene. Choose images and views from the actual
creative needs; do not stop at two images or require a fixed count. The document's
reference-asset image section records stable image IDs, visual settings, purpose and
related segments. Each segment names its image IDs, local image order and what
each image constrains, consistently with its complete prompt. Reuse the same
character or scene across segments; missing necessary images leave the plan
incomplete. Follow the manual workflow for the detailed reference design. Use the
Excel template only when the user explicitly requests XLSX; do not emit multiple
formats by default.
Deliver it before any video-generation call. Keep originals in the project. In Feishu,
return the project's actual video-plan board link through the existing topic result; do not send messages
yourself. If the Feishu API or permissions are unavailable, preserve the planned
content and report the concrete error rather than silently falling back to Word.
Explicitly text-only or initial-concept requests do not authorize generating
images. The manual plan describes composition, performance and shot continuity
without naming a video model or platform; employees choose their own generation
method. It requires no video-provider
selection, discovery or local video MCP session. End this task after delivering
the plan; a later trusted video upload continues the existing project and
post-production flow.

- **Analysis only:** "break down this video", "analyze the camera work", or
  "transcribe it" -> use the relevant registered analysis tools. Ground claims in
  actual frames, scene timing and audio/transcript evidence. Report partial or
  unavailable analysis honestly. Deliver the requested analysis without starting
  a production pipeline, requesting a production concept approval, or generating
  paid media.
- **Reference-driven creation:** "analyze this and make something similar" ->
  analyze the reference first using the workflow below, then select a production
  pipeline. The analysis may proceed directly; production follows the user's
  actual request and existing approvals.
- **Source-footage editing:** "edit this footage" / "cut this into clips" ->
  use `source_media_review` and the appropriate footage-led pipeline.
- **New production:** "make a product promo" -> follow Rule Zero. Decide duration
  and structure from the communication goal and available material; a provider's
  single-clip duration is not the duration of the complete film.

For Feishu, accept only Bridge-frozen inputs or the exact trusted media explicitly
referenced in the same conversation. Keep analysis evidence and subsequent
production linked to that source and reuse valid analysis and approved plans on
continuation. Do not search another workspace for similar historical media. Return
new local artifacts to Worker for registration and delivery; do not upload or send
Feishu results from the business workflow. When asking for video-sample approval, return
the validated sample video as a deliverable artifact in the current response,
even when the full production is paused. A localhost/Backlot link or text saying
the sample passed does not replace the video. Preserve the awaiting-approval
state and the existing executor result contract; do not mark the full film complete.
Explicit user workflow choices take
precedence. Missing project access or capabilities must be reported as concrete
blockers, not a request for the user to supply a local project directory.

### Reference-driven analysis and creation

When the user provides a **video URL or local video file as inspiration** — for example:

- "Can you make a video like this?"
- "I love this YouTube Short. Make me something similar."
- "Use this Reel as a reference."

— do **not** treat this as a generic web-search or prompt-writing request.

This is a first-class workflow in OpenMontage.

### Required behavior

1. **Read:** `skills/meta/video-reference-analyst.md`
2. **Run the reference analysis workflow** using the local analysis tools (`video_analyzer`, transcript extraction, scene detection, frame sampling)
3. **Produce a grounded summary** of what the reference is doing:
   - content
   - pacing
   - structure
   - style
   - what makes it work
4. **Then** run normal capability audit and pipeline selection
5. Present **2-3 differentiated concepts** for the user's version — not a carbon copy

For every reference-driven production, also read
`skills/meta/reference-production-handoff.md`. Preserve the reference's
communication logic in `proposal_packet.metadata.reference_adaptation` and
carry its approved revision through each stage. A reference summary, a suggested pipeline,
or completed checkpoints alone do not prove this handoff. Review script,
performance and cross-shot continuity against the plan, separately from
technical media validity. This applies equally to Feishu and local requests.

### Important distinction

- **Reference-driven request:** "make me something like this" -> use `video-reference-analyst.md`
- **Source-footage request:** "edit this footage" / "cut this into clips" -> use `source_media_review` and the appropriate footage-led pipeline

If a model misses this distinction, it will often fall back to plain search + guesswork. That is incorrect for OpenMontage.

## Rule Zero — All Production Goes Through a Pipeline

**Every video production request MUST go through the pipeline system. No exceptions.**

When the user asks to make, create, produce, or generate any video content — a trailer, explainer, clip, animation, or any other video — the agent must:

1. **Identify the pipeline.** Match the request to one of the pipelines in `pipeline_defs/`. If unclear, ask the user.
2. **Read the pipeline manifest.** `pipeline_defs/<pipeline>.yaml` — know the stages, tools, and quality gates.
3. **Run preflight.** Discover available tools via the registry. Present the capability menu.
4. **Execute stage by stage.** For EACH stage, read the stage director skill (`skills/pipelines/<pipeline>/<stage>-director.md`) BEFORE doing any work in that stage.
5. **Read Layer 3 skills before calling tools.** Before using any tool with an `agent_skills` field, read the referenced skill in `.agents/skills/`. These contain provider-specific prompting guidance, parameter optimization, and quality techniques that dramatically improve output.

**Do NOT:**
- Write ad-hoc Python scripts to call tools directly
- Skip the pipeline and go straight to API calls
- Generate assets without reading the stage director skill first
- Use a tool without checking its Layer 3 skill for prompting guidance
- Bypass preflight, checkpoints, or review

The intelligence is in the skills, not in improvised code. An agent that reads the director skills and Layer 3 knowledge will produce significantly better output than one that calls tools directly with generic prompts.

## What OpenMontage Is

OpenMontage is an instruction-driven video production system. The AI agent IS the intelligence — it reads instructions (pipeline manifests + stage director skills + meta skills) and drives the pipeline using tools.

```
Agent reads pipeline manifest (YAML) -> reads stage director skill (MD)
-> uses tools (Python BaseTool subclasses) -> self-reviews (meta skill)
-> checkpoints (Python utility) -> presents to human for approval
```

**Python = tools + persistence.** No orchestration logic, creative decisions, review logic, or checkpoint policy in Python code. The agent makes those decisions guided by instructions.

Core loop:

1. Select a pipeline.
2. Run preflight.
3. Discover real tools from the registry.
4. Present the user with concepts, tool plan, production plan, and cost.
5. Execute stage by stage with checkpoints.

## Decision Communication Contract

For any meaningful production decision, the agent must communicate the decision before acting. The user should never have to infer which provider, model, or render path was chosen after the fact.

### Announce Before Execution

When first choosing the production route, briefly state:

- the exact tool name,
- the provider,
- the model or provider variant,
- the reason it was chosen,
- whether it is a sample or a batch run.

Once selected, reuse that route without repeating this announcement for each
shot, poll, continuation or prompt refinement. Progress updates should describe
the work and result. Retain exact provider/model identity in the request and
receipts; an unchanged selection is not a new decision or approval request.

### Ask Before Major Changes

The agent must ask the user before changing any major production choice, including:

- switching provider,
- switching model family or provider variant,
- switching from video-led to still-led treatment,
- switching composition engine when that changes the output character,
- dropping narration, music, or other approved creative elements,
- changing from sample mode to batch mode.

Minor prompt refinements inside an already approved provider/model path do not require separate approval unless they materially change the creative direction.

### Re-log Changed Decisions (Binding)

The `decision_log` is the board's Decisions rail and the run's audit trail. It is **append-only history, not a scratchpad.** When a choice you already logged changes mid-run — the user swaps the voice, you switch provider/model/runtime/music, or a fallback overrides an earlier pick — you MUST **append a new `decision_log` entry** for the new choice, reusing the **same `category` AND the same `subject`** (e.g. `category: "voice_selection"`, `subject: "Narration TTS provider"`), with the superseded option moved into `options_considered` and `rejected_because` noting it was changed.

Editing only a downstream artifact (the `asset_manifest`, a prop) while leaving the old decision in the log is a defect: the board keeps showing the stale choice (e.g. `voice → openai_onyx` after the user moved to Chirp3). The board identifies a decision by its **(category, subject) pair** and renders the latest entry for that pair as current (tagged "revised") — so the fix is to append the new entry with an identical `subject`, never to silently mutate the old one or reword the subject (a reworded subject reads as a different decision and both will show). Keeping distinct decisions in one category (e.g. TTS vs image `provider_selection`) is exactly why the pair, not the category alone, is the key. This applies at every stage, not just `idea`.

### Default Composition Runtime

New productions use **Remotion**. Check its availability, then lock
`proposal_packet.production_plan.render_runtime="remotion"` and carry the same
value into `edit_decisions`. Do not present a Remotion/HyperFrames/FFmpeg menu
or ask for another technical confirmation. A `render_runtime_selection` entry
may record Remotion as the single considered option; do not invent alternatives.
This default does not change creative direction or existing production approvals.

`video_compose.get_info()["user_facing_render_runtimes"]` is the new-work entry;
`render_engines` remains the actual internal availability map for compatibility.
If Remotion is unavailable, report the missing dependency and stop that render.
Do not automatically switch engines.

Existing projects retain their explicit runtime locks. HyperFrames remains a
compatibility path for those projects or an explicit user request to work in
that runtime. Selecting a specialized pipeline alone does not override this
default. If a rig/HTML workflow has no Remotion handoff, report the actual gap
rather than migrating its assets or choosing HyperFrames silently. FFmpeg may
still perform editing, audio processing and packaging. Runtime changes retain
their existing approval, decision-log and validation requirements.

### Composition Authoring Mode — Templated vs Atelier

Orthogonal to *runtime* is *authoring mode*: **how** the composition is built. Present it as its own proposal decision and log it in `decision_log` (`category: "composition_mode"`).

- **Templated** — assemble the stock `cut.type` scene-types (`text_card`, `stat_card`, `bar_chart`, …) into the `Explainer`/`CinematicRenderer` compositions. Fast, cheap, reliable — and the reason most videos look alike. Right for batch output, localization variants, quick drafts, and low-stakes internal clips.
- **Atelier** — **hand-author the composition from scratch**: bespoke scenes, a one-off theme, and motion written for this piece, rendered via `composition_mode: "atelier"` (see `video_compose` → `_render_via_atelier`). No reusable creative components; a fresh visual language every time.

**Default to atelier for hero work** — marketing, launches, brand pieces, any single-deliverable explainer that must impress. The deciding rule: *reuse engine knowledge, never creative components.* In atelier mode the stock scene-type catalog, `hyperframes-registry` blocks, fixtures, and finished components are **off-limits** — they are frozen looks that reintroduce sameness. Before building, route through **`skills/meta/taste-direction.md`** to set the design read and taste dials, then **`skills/meta/bespoke-composition.md`**, which sequences: art direction (`visual-style`) → motion principles (Disney 12 via `framer-motion`/`lottie-bodymovin`) → engine mechanics (`remotion-best-practices` + the stock components read *only as a mechanics codex*) → render via the atelier path. Close with a **distinctness review**: *could this be any other product's video? does it reuse a look I've made before?* — the inverse of "does it match the reference." Atelier costs more tokens and iteration than templated; say so at proposal so the user opts in knowingly.

### Escalate Blockers Explicitly

When a blocker occurs, the agent must surface it immediately using this structure:

1. What was attempted
2. What failed
3. Whether the issue is auth, provider access, tool bug, or prompt/design quality
4. What options exist next
5. Which option the agent recommends, with reasoning

Do not continue with a substitute path until the user approves.

### Recommendation Style

When asking the user to choose, do not just list options. The agent should:

- provide the shortlist,
- explain the tradeoffs briefly,
- recommend one option,
- wait for approval before proceeding.

### No Unilateral Substitutions

If the approved path is blocked, the agent may investigate and prepare alternatives, but may not execute those alternatives without user approval.

This applies especially to:

- provider swaps,
- model swaps,
- fallback tools,
- prompt-only substitutes for reference-driven generation,
- still-image animatics in place of true motion.

## Orchestrator

The agent itself orchestrates the production state machine:

`research -> proposal -> script -> scene_plan -> assets -> edit -> compose`

The agent:

1. Reads the pipeline manifest (`pipeline_defs/*.yaml`) to know the process
2. Calls `checkpoint.get_next_stage()` to find where to resume
3. Reads the stage's director skill (`skills/pipelines/<pipeline>/<stage>-director.md`) to know HOW
4. Uses tools (`tools/`) for concrete capabilities
5. Self-reviews using the reviewer meta skill (`skills/meta/reviewer.md`)
6. Checkpoints via the checkpoint protocol (`skills/meta/checkpoint-protocol.md`)
7. Presents to human for approval when `human_approval_default: true`

Infrastructure files:

- `lib/checkpoint.py` — read/write checkpoints, stage validation
- `tools/cost_tracker.py` — budget governance
- `lib/pipeline_loader.py` — manifest loading and helpers

## Project Directory Convention

Every production run creates a project workspace under `projects/`. This directory is gitignored — all generated assets are regenerable.

```
projects/<project-name>/
├── artifacts/          # JSON artifacts from each stage (research_brief, script, scene_plan, etc.)
├── assets/
│   ├── images/         # Generated images (PNG)
│   ├── video/          # Generated video clips (MP4)
│   ├── audio/          # Narration segments + final mix (MP3/WAV)
│   ├── music/          # Background music track (MP3)
│   └── subtitles.srt   # Generated subtitles
└── renders/
    └── final.mp4       # Final rendered video (the deliverable)
```

**Naming convention**: Use kebab-case derived from the video title (e.g., `hidden-math-of-nature`, `how-music-rewires-brain`).

At pipeline initialization, before any stage runs:

1. **Initialize the workspace**: `python -c "from lib.checkpoint import init_project; init_project('<project-id>', title='<Title>', pipeline_type='<pipeline>')"` — creates the layout above and writes `project.json` (the marker the Backlot board reads).
2. **Automatic live board**: `init_project` starts Backlot if needed and opens the project's live board for canonical production workspaces, including reinitialization on task continuation. No separate open command is needed after initialization. For an already initialized project resumed without calling `init_project`, run `python -m backlot open <project-id>` once before continuing. Include the returned board URL in the first progress update so a Feishu user can reopen it. The URL is local to this computer, not a public or phone-accessible site. Alternate workspace roots stay quiet by default; `open_board=False` is the explicit opt-out. If the board fails, report its availability and continue production — it remains an observer, never a blocker, and derives progress from disk.

All tools and agents must write outputs to these paths — **always pass an explicit `output_path` under `projects/<project-id>/`**. Assets written to the repo root, cwd, or temp dirs are invisible to the user's board and violate the workspace contract.

**This applies to atelier and HyperFrames-skill runs too**: hand-authored compositions still write the canonical artifacts they have (script or beats-plan, scene_plan-equivalent, asset manifest) plus checkpoints into `projects/<project-id>/`. The board is runtime-agnostic; only runs that skip the artifacts get a degraded board.

## Music Library

Users can place royalty-free music tracks in `music_library/` (gitignored). The asset director will check this folder before falling back to API-based music generation.

```
music_library/
├── ambient_track.mp3
├── cinematic_epic.mp3
└── ...
```

If the folder has tracks, the proposal and asset stages should present them as options alongside generated music. See the proposal-director and asset-director skills for details.

## Available Pipelines

| Pipeline | Best For | Stability |
|----------|----------|-----------|
| `animated-explainer` | Topic to fully generated explainer | production |
| `talking-head` | Footage-led speaker videos | beta |
| `screen-demo` | Screen recordings and walkthroughs | production |
| `clip-factory` | Many clips from one long source | beta |
| `podcast-repurpose` | Podcast highlights and derivatives | beta |
| `cinematic` | Trailer, teaser, and mood-led edits | production |
| `animation` | Motion-graphics and animation-first videos | production |
| `character-animation` | Local rigged cartoon characters and reusable character acting | beta |
| `hybrid` | Source footage plus support visuals | production |
| `avatar-spokesperson` | Presenter-led avatar or lip-sync videos | production |
| `localization-dub` | Subtitle, dub, and translated variants | beta |
| `framework-smoke` | Test: minimal 2-stage smoke test | test |

> **Beta pipelines** have not been fully audited. They work, but expect rough edges. Mention this when the user selects one.

## Mandatory Preflight

Do this before any creative work. **Use `provider_menu_summary()` first — it's the human-ready rollup.** The raw `support_envelope()` dump is a firehose (megabytes of JSON on a well-configured machine); pasting it into chat will bury the user.

```bash
python -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(), indent=2))
"
```

The summary returns four fields the agent should translate into plain language:

- `composition_runtimes` — actual availability booleans for `ffmpeg`, `remotion`, `hyperframes`, retained for compatibility checks. New-work planning follows Default Composition Runtime and exposes only Remotion.
- `capabilities[]` — one entry per capability family with `configured / total` counts and provider lists. Ready-made for the "N of M configured" menu.
- `setup_offers[]` — unavailable tools whose install is a 1-minute env-var fix. Lead with these when offering upgrades.
- `runtime_warnings[]` — missing-runtime signals for preflight. Surface warnings relevant to the locked runtime; for new work report Remotion gaps. HyperFrames warnings belong to its existing or explicitly requested compatibility path.

Then, for deeper inspection (only when the summary isn't enough):

```bash
# Full menu — grouped available/unavailable per capability.
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"

# Raw envelope — every tool's full contract. Slow/firehose; use for debugging only.
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
```

Then:

1. Read the selected manifest in `pipeline_defs/`.
2. Check every `required_tools` entry against the registry.
3. Check `fallback_tools` for unavailable tools.
4. Report one of: `passed`, `degraded`, or `blocked`.
5. Do not start production until the user understands the real capability envelope.

### Provider Menu (Mandatory at Preflight)

Already fetched via `provider_menu_summary()` above. Read that output and **present it to the user as a capability menu**, not as a flat tool list. Use `provider_menu()` directly only when you need the per-tool detail the summary collapses.

**How to present:**

```
YOUR CAPABILITIES

  Video Generation:  0/13 configured
  Image Generation:  1/7 configured
  Text-to-Speech:    1/3 configured
  Music Generation:  1/1 configured
  Composition:       3/3 configured (FFmpeg, video_stitch, video_trimmer)

  You can produce videos now with images + TTS + FFmpeg.
  Quick upgrades available — see below.
```

For EACH capability with unavailable providers, read the `install_instructions` field from the menu output and present setup options grouped by effort:

```
QUICK SETUP OPTIONS (1-minute each — set an env var in .env)

  Video Generation (0/13 -> unlock the biggest upgrade):
    Each unavailable provider lists its own install_instructions.
    Read them from the provider_menu output and present grouped by env var.
    Example: if 3 tools need FAL_KEY, group them: "FAL_KEY unlocks 3 providers"

  Image Generation (1/7 -> more style options):
    Same pattern — read install_instructions from each unavailable tool.

  Text-to-Speech (1/3):
    Same pattern.

LOCAL OPTIONS (free, needs hardware):
  Tools with runtime=LOCAL or runtime=LOCAL_GPU — read from the menu.

Already Available:
  List what's working. The user should feel good about what they have.
```

**Rules:**
- Do NOT hardcode provider names, API key names, or setup URLs in your prompts.
  Read them from the registry's `install_instructions` field on each tool.
- Always show the ratio: "X of Y configured" — this makes breadth visible.
- Group by capability, not by individual tool.
- Show what they CAN do now, then what they COULD unlock.
- If the user declines setup, proceed with the best available path — no nagging.
- If a tool shares an env var with others, group them (read from `dependencies` field).

### Setup Offer Protocol

When tools are `UNAVAILABLE` but can be fixed with simple configuration, **offer the user setup help instead of silently working around the limitation.** Many tools are one env var away from working.

| Fix Complexity | Action |
|----------------|--------|
| **1-minute fix** (env var) | Offer to help configure now — read `install_instructions` from the tool |
| **5-minute fix** (install) | Explain what to install and why — read `install_instructions` from the tool |
| **Complex fix** (GPU, model download) | Note the limitation, explain what it would unlock, move on |

**Rules:**
- Always tell the user what they're missing AND what they'd gain
- Show the cost difference (free local vs. paid API)
- If the user declines setup, proceed with the best available path — no nagging
- Group related fixes (tools sharing the same env var dependency)

### Composition Runtimes (Inside video_compose)

`video_compose` retains **three** internal render engines for compatibility.
New compositions default to Remotion and lock that value in
`edit_decisions.render_runtime`; existing explicit locks remain unchanged.
The following is an internal availability check, not a user-facing engine menu:

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
info = registry._tools['video_compose'].get_info()
print('Render engines:', info.get('render_engines'))
print('Remotion note:', info.get('remotion_note'))
print('HyperFrames note:', info.get('hyperframes_note'))
"
```

| Engine | Used For | Requires |
|--------|----------|----------|
| **FFmpeg** | Video-only cuts, concat, trim, subtitle burn | `ffmpeg` binary (always available) |
| **Remotion** | React-based composition: still images → animated video, text cards, stat cards, charts, callouts, comparisons, transitions with spring physics, word-level caption burn, TalkingHead avatar | Node.js (`npx`) + `remotion-composer/` + `node_modules` |
| **HyperFrames** | HTML/CSS/GSAP composition: kinetic typography, product promos, launch reels, website-to-video, registry-block-driven scenes, SVG character rigs | Node.js ≥ 22 + FFmpeg + `npx` (consumed via `npx hyperframes`) |

`render_runtime` is **locked at proposal** (`proposal_packet.production_plan.render_runtime`) and **carried through edit_decisions unchanged**. `video_compose` routes based on this field; silent runtime swaps are forbidden. If the chosen runtime becomes unavailable at compose time, surface a structured blocker per "Escalate Blockers Explicitly" above. Follow Default Composition Runtime for new work; `skills/core/hyperframes.md` covers only existing or explicitly requested HyperFrames compatibility.

### Critical Rule: Motion-Required Requests

For any request where the deliverable inherently depends on motion rather than static coverage, treat motion as a hard requirement. Examples:

- sci-fi trailers,
- cinematic teasers built from generated clips,
- hype edits,
- avatar or agent videos,
- any brief whose promise depends on moving shots rather than still frames.

For these requests:

- The `render_runtime` chosen at proposal (Remotion, HyperFrames, or FFmpeg) must be confirmed available up front if the planned visual treatment depends on it.
- Still-image fallback is forbidden. Do not quietly convert the job into a Ken Burns teaser, animatic, or slide-based video.
- FFmpeg-only fallback is forbidden when it changes the approved deliverable from motion-led video to still-led video.
- **Silent runtime swap is forbidden.** If `render_runtime="hyperframes"` was locked and HyperFrames is unavailable, do NOT route to Remotion instead. Surface the blocker, propose options, get user approval, log a `render_runtime_selection` decision — then proceed.
- Bubble critical issues immediately. If the chosen runtime is unavailable, fails to render, or provider clip generation fails in a way that blocks the approved treatment, stop and tell the user before proceeding.
- Do not spend more tokens or time on downgraded output unless the user explicitly approves the downgrade as an animatic or proof-of-concept.

**When Remotion is available**, the agent should design production plans around it:
- Explainer videos with `flat-motion-graphics` playbook -> Remotion animated scenes, not Ken Burns
- Data-driven videos -> Remotion stat cards and charts, not static image screenshots
- Any pipeline using still images -> Remotion spring animations, not FFmpeg pan-and-zoom
- **Screen demos of a CLI/terminal/install flow -> `TerminalScene` (synthetic screen recording), not OS-level capture.** See `.agents/skills/synthetic-screen-recording/SKILL.md`. Faster, deterministic, privacy-safe. Use real capture (`screen_recorder`, `cap_recorder`, `playwright-recording`) only when the demo is a real app UI or requires unpredictable live behavior.

### Remotion scene types available in `remotion-composer/`

See `remotion-composer/SCENE_TYPES.md` for the authoritative list and their cut schemas. Current scene types usable via `cut.type`:
`text_card`, `stat_card`, `callout`, `comparison`, `hero_title`, `terminal_scene`, `anime_scene`, `bar_chart`, `line_chart`, `pie_chart`, `kpi_grid`, `progress_bar`. Overlay types include `section_title`, `stat_reveal`, `hero_title`, `provider_chip`.

These stock scene-types are the **templated** path — fast and reliable, but they are why videos look alike. For **hero work, prefer atelier mode** (hand-authored composition) over this catalog; read those types as a *mechanics codex*, not a menu to assemble. See "Composition Authoring Mode" above and `skills/meta/bespoke-composition.md`.

**When Remotion is NOT available**, new compositions must report the gap and stop.
A missing runtime lock is also a blocker; it does not authorize FFmpeg Ken Burns
or another runtime. FFmpeg remains available for standalone editing and existing
explicitly locked work.

When `render_runtime="hyperframes"` is locked and HyperFrames is unavailable (Node < 22, missing `ffmpeg`/`npx`, or `hyperframes doctor` reports issues), that's also a blocker. Do not substitute Remotion or FFmpeg without user approval + a logged `render_runtime_selection` decision.

Routing is automatic — `video_compose` reads `edit_decisions.render_runtime` and dispatches to the matching engine (`_render_via_hyperframes`, `_remotion_render`, or `_render_via_ffmpeg`). New compositions use Remotion, including motion graphics. Other dispatch paths preserve existing explicit locks or an explicit user request for that runtime; availability and visual style alone do not authorize a switch.

## Capability Discovery

OpenMontage uses two layers for capability choice:

- selector tools: capability-level routing such as `tts_selector` and `video_selector`
- provider tools: concrete tools discovered via the registry that call a specific backend

Always inspect the registry first:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog(), indent=2))"
```

For finalist tools inspect:

- `capability`
- `provider`
- `usage_location`
- `supports`
- `fallback_tools`
- `related_skills`

Do not rely on memory or old docs when the registry can answer it.

## Tool Families

**Do not maintain hardcoded tool lists.** Always query the registry at runtime:

```bash
# See all tools grouped by capability (TTS, video_generation, image_generation, etc.)
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"

# See all tools grouped by provider (elevenlabs, openai, ffmpeg, etc.)
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog(), indent=2))"
```

Key capability families to look for in the output:

- **tts** — Text-to-speech providers. Route via `tts_selector`.
- **video_generation** — Video generation providers (cloud, local GPU, stock). Route via `video_selector`.
- **image_generation** — Image generation providers (cloud, local GPU, stock). Route via `image_selector`.
- **music_generation** — Music and sound effect generation.
- **video_post** — Composition, stitching, trimming (FFmpeg-based, always local).
- **audio_processing** — Mixing, enhancement (FFmpeg-based, always local).
- **analysis** — Transcription, scene detection, frame sampling.
- **avatar** — Talking head and lip sync generation.
- **character_animation** — Local character specs, SVG rigs, pose libraries, action timelines, previews, and QA.
- **3d_world_generation** — Local semantic terrain, procedural biome scattering, explicit landmarks, diagnostic passes, and deterministic HyperFrames/Three.js camera fly-throughs. Route through `threejs_world` and read `skills/creative/3d-world-generation.md` plus `.agents/skills/threejs-world-generation/SKILL.md`.
- **3d_asset_acquisition** — Rights-safe GLTF/GLB catalogs for production-tier Three.js worlds. Route through `threejs_asset_catalog`; never substitute blockout primitives for a requested detailed or reference-grade environment.
- **3d_asset_generation** — Unique textured/PBR meshes from text or concept images. Route text-described hero assets through `atlas_3d`, image-conditioned assets and regional object extraction through `fal_3d`, and read `.agents/skills/3d-asset-generation/SKILL.md`. Announce provider/model/unit cost before every first paid call and sample before batching.
- **3d_world_rendering** — Production assembly, terrain, lighting, materials, camera, and image-sequence rendering in Blender. Route through `blender_world`; use Three.js for interactive/blockout review, not as a substitute for Blender when reference-grade scene density is requested.
- **enhancement** — Upscale, background removal, face enhance, color grading.

Each tool in the registry declares `best_for`, `install_instructions`, `runtime` (LOCAL, API, LOCAL_GPU, HYBRID), and `status`. Read these fields — do not assume tool strengths from memory.

### Tool Class Naming Convention

All tool classes use **PascalCase without a "Tool" suffix**. When importing tools in Python:

| Module | Class Name | NOT |
|--------|-----------|-----|
| `tools.audio.music_gen` | `MusicGen` | ~~MusicGenTool~~ |
| `tools.video.video_compose` | `VideoCompose` | ~~VideoComposeTool~~ |
| `tools.audio.audio_mixer` | `AudioMixer` | ~~AudioMixerTool~~ |
| `tools.tts.elevenlabs_tts` | `ElevenLabsTTS` | ~~ElevenLabsTTSTool~~ |
| `tools.analysis.transcriber` | `Transcriber` | ~~TranscriberTool~~ |
| `tools.subtitle.subtitle_gen` | `SubtitleGen` | ~~SubtitleGenTool~~ |

When in doubt, check: `grep "^class " tools/<path>.py`

All tools call via `.execute(params_dict)` (returns `ToolResult` with `.success`, `.data`, `.error`), NOT `.run()`.

### Selector Pattern

Three selector tools abstract multi-provider capabilities. **Selectors auto-discover providers from the registry.** Adding a new provider tool automatically makes it available through the selector — no selector code changes needed.

| Selector | Routes to | How it discovers |
|----------|-----------|-----------------|
| `tts_selector` | All tools with `capability="tts"` (ElevenLabs, Google TTS, OpenAI, Piper, Azure, fish.audio) | `registry.get_by_capability("tts")` |
| `image_selector` | All tools with `capability="image_generation"` (FLUX, Google Imagen, GPT Image, Recraft, etc.) | `registry.get_by_capability("image_generation")` |
| `video_selector` | All tools with `capability="video_generation"` | `registry.get_by_capability("video_generation")` |

Selectors route based on: user preference > availability > discovery order. They adapt input schemas between providers transparently.

Video generation keeps scripts, characters, scenes and reference assets in the
same canonical project artifacts. Only the final generation request is mapped
to the selected MCP/API adapter. Follow the
[video provider extension contract](docs/references/video-provider-extension.md)
for the optional `prepare_video_request` hook and existing registry discovery.
It adapts parameters without rewriting creative content, changing the selected
provider/model, or starting generation during preparation. Preserve native
task status and receipts; a new adapter is not usable until its actual contract
and runtime are verified.

## User-Facing Planning Protocol

Production is completion-driven. Cost and usage reporting exists to make paid
operations visible and prevent duplicate submissions; it is not a default stop
condition. Do not invent a monetary budget or whole-production deadline. Respect user caps
and configured revision/send-back limits; at those limits preserve unresolved
artifacts and report the blocker, never auto-pass an unmet delivery requirement. For Token Plan providers,
record unknown USD/tokens as `null`, never as zero.

Provider capability limits are per-call planning constraints, not whole-video
limits. Split long work into shots and compose them. Persist an attempt ledger
and resume ambiguous/non-terminal tasks before any new paid submission. A
generated clip becomes usable only after model-owned semantic review of actual
media; deterministic probes validate technical properties but cannot approve
identity or action realization.

Before committing to execution, present:

1. `4-5` concept directions when the brief is still open.
2. Recommended pipeline.
3. Recommended tool path.
4. Alternative tool paths that are actually available.
5. Cost estimate and quality tradeoffs.
6. **Music plan** — mandatory for every pipeline that has audio. See below.
7. Production plan by stage.
8. Complete-plan board confirmation at scene_plan before video/audio generation.

If a user prefers a specific vendor and that tool is available, surface it directly. Do not hide provider choice.

### Music Plan (Mandatory)

Music is a critical part of any video. **Surface the music situation to the user at proposal/idea time** — do not silently defer it to the asset stage where a failure becomes expensive.

Check music availability in this order and present the options:

Reuse a music decision the user has already approved, including accepted
project-local tracks; do not reopen it or acquire another track at compose time.

1. **User music library:** Check `registry.get_by_capability("music_library")` and inspect `music_library/`. If tracks exist, list durations and let the user pick one.
2. **Royalty-free search:** Check `registry.get_by_capability("music_search")` for configured search/download tools. Report licensing constraints and whether a key is required.
3. **Music generation APIs:** Check `registry.get_by_capability("music_generation")`. Report status, quota, cost, and quality tradeoffs honestly.
4. **Bring your own:** Note that the user can provide a track (for example from YouTube Audio Library or Jamendo) through the `music_library/` drop path.

**Always present the user with explicit choices:**
- Use a track from their library (which one?)
- Use a selected search result with its license and attribution requirements
- Provide a different track (drop it in `music_library/`)
- Generate one via API (if available — name the provider and cost)
- Proceed without music

**If no music source is available:** Tell the user explicitly. Do NOT let this surface as a surprise at the asset stage.

Record the music decision in the proposal/brief artifact so the asset director knows what to do.

For music direction, section changes, native-audio boundaries and actual mixing
handoff, follow [the background music workflow](docs/references/music-workflow.md).
A coherent track can span the film with changes in level or silence; it need not
change at every cut. Metadata plans and `ducking` flags do not prove execution.

## Pipeline Asset Expectations

Each pipeline manifest's `tools_available` field declares what tools a stage can use. Use selectors for multi-provider capabilities — the selector handles routing to whatever is available. Read the pipeline manifest for the authoritative list per stage.

## Stage Agents

Each stage produces one canonical artifact that becomes the contract for the next stage. The stage director skill teaches the agent HOW to produce it.

| Stage | Director Skill | Canonical output | Core quality bar |
|------|---------------|------------------|------------------|
| `idea` | `*-director.md` | `brief` | Clear hook, target platform, duration, tone, and user intent |
| `script` | `*-director.md` | `script` | Structured sections, valid timing, coherent narration |
| `scene_plan` | `*-director.md` | `scene_plan` | Ordered scenes, timings, asset requirements |
| `assets` | `*-director.md` | `asset_manifest` | Provenance, paths, model/tool metadata, scene linkage |
| `edit` | `*-director.md` | `edit_decisions` | Concrete cuts, overlays, subtitle/music decisions |
| `compose` | `*-director.md` | `render_report` | Output paths, encoding profile, verification notes |

Stage contract rules:

- A completed or awaiting-human checkpoint must include the stage's canonical artifact.
- Canonical artifacts must validate against the JSON schema in `schemas/artifacts/`.
- Non-canonical outputs such as media files belong in stage-specific directories.
- Tools should record seeds/model versions for reproducibility.

## Reviewer Protocol

The reviewer is a meta skill (`skills/meta/reviewer.md`) — advisory, never directly blocks progression.

- Self-review after every stage execution, before checkpointing.
- Load `review_focus` items from the pipeline manifest for the current stage.
- Use the pipeline's configured revision/send-back limits (default three). At the limit, preserve the current artifacts and report unresolved issues; do not auto-pass an unmet delivery requirement. Resume only with a changed repair plan or user direction.
- Findings categorized: critical (must fix), suggestion (should fix), nitpick (nice-to-have).
- Critical findings -> fix and re-review. Suggestions -> note and proceed.
- Check playbook `quality_rules` as constraints, not suggestions.

## Human Checkpoint Protocol

### Complete-plan confirmation (current production default)

All non-test production manifests use the existing `scene_plan` stage as the
single human production-confirmation gate. Research, proposal/idea, script and
other design stages still execute, review and checkpoint in order, but proceed
internally without separate approval prompts. During scene_plan, prepare/reuse
the necessary actual reference images and publish the complete standalone plan
board: full story/script, shot actions, timing, image roles and complete prompts.
No video, TTS, music generation or sample render occurs before this gate.
Store the board URL, plan/source revision hashes, reference identities and
automatic/manual/plan-only choice in existing scene-plan/checkpoint metadata.
Write `awaiting_human`, deliver the board and stop; approval applies to that
specific complete revision. Then write `completed`, `human_approved=True`.

For approved automatic production, execute all planned shots, internal asset
review, repair and post-production without a separate ten-second sample or
assets approval pause. Manual production waits for trusted returned clips in
the same project; plan-only delivery ends without generating video. Internal
quality checks, unknown-submission reconciliation, budget/provider constraints
and final review remain required. Material changes outside the approved plan
require user direction. Platform publication retains its own authorization.
An explicitly locked historical run keeps its recorded approval policy; do not
rewrite old checkpoints or claim the new policy was used for past production.

The checkpoint protocol meta skill (`skills/meta/checkpoint-protocol.md`) teaches the agent when to pause:

- Read `human_approval_default` from the pipeline manifest per stage. **The manifest value is binding** — never re-judge it. `lib/checkpoint.py` enforces this: a gated stage cannot be written `completed` without `human_approved=True`.
- Current production gates are `scene_plan` (complete plan board) and `publish` where the manifest has one. Assets are reviewed internally scene by scene before compose; they do not trigger another default human confirmation. The manifest remains the binding authority.
- When approval is required: write the checkpoint as `awaiting_human`, present artifact summary, review findings, and cost snapshot — then **END YOUR TURN**. Doing further pipeline work in the same response is a gate violation.
- **Approval is per-gate.** An early "go ahead" never covers later gates; explicit full-run pre-authorization must be recorded as a `decision_log` entry (`category: "approval_policy"`) to count.
- Wait for human to approve, request revision, or abort.

## Communication Protocol

Agents coordinate through canonical JSON artifacts, checkpoints, pipeline manifests, and the tool registry.

Primary files:

- Artifact schemas: `schemas/artifacts/`
- Checkpoint schema: `schemas/checkpoints/checkpoint.schema.json`
- Pipeline manifest schema: `schemas/pipelines/pipeline_manifest.schema.json`
- Pipeline manifests: `pipeline_defs/`
- Style playbooks: `styles/*.yaml` (validated by `schemas/styles/playbook.schema.json`)
- Tool contract: `tools/base_tool.py`
- Tool registry: `tools/tool_registry.py`
- Stage director skills: `skills/pipelines/<pipeline>/<stage>-director.md`
- Meta skills: `skills/meta/*.md`

Checkpoint rules:

- Checkpoints live at `projects/<project_id>/checkpoint_<stage>.json` (the project workspace — this is what the Backlot board watches).
- `status` may be `completed`, `failed`, `awaiting_human`, or `in_progress`.
- Write an `in_progress` checkpoint on entering each stage; during `assets`/`compose`, refresh `metadata.partial_progress` after each completed scene/asset unit — this powers live progress on the board.
- `completed` and `awaiting_human` checkpoints must include the canonical artifact.
- A gated stage (`human_approval_default: true`) can only be written `completed` with `human_approved=True` — the writer raises a GATE VIOLATION otherwise.
- Superseded checkpoints are archived automatically to `projects/<project_id>/history/` — stage re-runs never destroy run history.
- Invalid checkpoints or invalid canonical artifacts are contract violations and should fail fast.

Pipeline manifest rules:

- Pipelines are declarative YAML manifests in `pipeline_defs/`.
- Stages declare: `skill` (director skill path), `produces`, `tools_available`, `review_focus`, `success_criteria`, `human_approval_default`.
- Adding a new pipeline requires a manifest + stage director skills.

Tool rules:

- Every production tool must inherit from `BaseTool`.
- Tool discovery flows through the registry, not ad hoc imports.
- Support-envelope reporting is the source of truth for capability, status, and resource requirements.

## Style Playbooks

| Playbook | Best For |
|----------|----------|
| `clean-professional` | Corporate, educational, SaaS |
| `premium-minimalist` | Investor updates, expert explainers, product narratives |
| `flat-motion-graphics` | Social media, TikTok, startups |
| `minimalist-diagram` | Technical deep-dives, architecture |
| `ink-sketch` (Ink Theater) | Hand-drawn ink-on-white doodle animation; a character that draws itself, walks, dances; contraption explainers |

For custom, atelier, brand, launch, or hero work, read `skills/meta/taste-direction.md` before choosing a playbook. Carry its `taste_profile` into the proposal so later stages can preserve the design read, visual variance, motion intensity, information density, reference strategy, and anti-patterns.

### Hand-drawn "doodle" animation → Ink Theater / Ink Puppet

For any brief that wants a **hand-drawn ink doodle** look — "a sketch that comes to life", "a pencil / stick figure that walks or dances", "a little character that acts out the idea", whiteboard-doodle explainers — use the **Ink Theater** engine + **Ink Puppet** mocap system (`skills/creative/ink-theater.md`, `ink-theater/README.md`). It is a **style + reusable engine, not a new pipeline**: illustration / contraption pieces run on the `animation` pipeline; a mocap character (draws itself → walks / dances / waves via `InkPuppet.choreograph([...])`) runs on `character-animation`. Cross-tool entry points: **`/ink-art`** (create a vector doodle from scratch) and **`/animated-drawing`** (animate a *supplied* drawing with mocap — raster; `skills/creative/animated-drawing.md`). Never hand-tune character motion — the agent only chooses named mocap clips.

## Layer Map

OpenMontage has three instruction layers:

1. `tools/`
   What exists, what is available, cost, runtime, fallback, related skills.
2. `skills/`
   How OpenMontage wants those tools used in pipelines.
3. `.agents/skills/`
   Raw vendor or technology knowledge.

Reading order:

1. registry / tool contract — discover what's available
2. relevant pipeline or creative skill (Layer 2) — know HOW to use it in this context
3. underlying vendor skill (Layer 3) — **mandatory before calling any generation tool**

**Prefer skills over source code for tool usage.** Skills exist precisely so you don't need implementation details in the common case. Layer 2 tells you *what* and *when*. Layer 3 tells you *how*. For authoring prompts, choosing parameters, or understanding usage patterns, you should be reading skills — not `.py` files.

**Exception: debugging, audits, and verifying the governance contract.** When a skill and a tool disagree, or when something behaves differently than the skill claims, reading the tool source is fair game — that's often the only way to catch a silent-availability bug or a stale doc string. An audit that refuses to look at the implementation will miss exactly the bugs that matter most. If you do read source to debug, consider whether the finding belongs in a skill update afterward so the next agent doesn't need to repeat the dive.

**Layer 3 is not optional.** Every generation tool (video, image, TTS, music) has an `agent_skills` field listing its Layer 3 skills. These skills contain provider-specific prompt engineering, parameter tuning, and quality techniques. Read them before writing prompts. The difference between a generic prompt and a skill-informed prompt is the difference between "usable" and "cinematic."

Example: Before calling `kling_video`, follow the project entry, then read `skills/creative/video-gen-prompting.md` and the selected provider-specific skill for prompt structure, camera direction and parameters. The `ai-video-gen` skill only locates this project; it is not a prompting or approval policy.

### Layer 3 skills, by category

The `.agents/skills/` directory is large. When you're not coming in through a tool's `agent_skills` pointer, use this table to find the right file by *what you're trying to do*:

| Category | Skills |
|---|---|
| **Composition runtime** | `remotion`, `remotion-best-practices`, `synthetic-screen-recording` (fake terminal/UI demos via Remotion TerminalScene), `threejs-world-generation` (semantic terrain and free-viewpoint HyperFrames worlds) |
| **Animation knowledge (generic)** | `gsap-core`, `gsap-timeline`, `gsap-plugins` (SplitText / MorphSVG / DrawSVG / MotionPath / Flip / CustomEase), `gsap-utils`, `gsap-react`, `gsap-performance`, `gsap-scrolltrigger`, `gsap-frameworks`, `framer-motion` (Disney 12 principles), `lottie-bodymovin` (Lottie export) |
| **Character animation** | `character-rigging`, `svg-character-animation`, `pose-library-design`, `canvas-procedural-animation`, `character-animation-qa` |
| **Image generation** | `bfl-api`, `flux-best-practices` |
| **Video generation** | `seedance-2-0` (preferred premium default — cinematic, trailer, multi-shot, synced audio, lip-sync), `gemini-omni` (conversational video editing, reference tags, timecoded beats), `ai-video-gen`, `ltx2` |
| **Audio** | `elevenlabs`, `music`, `sound-effects`, `acestep`, `text-to-speech`, `azure-text-to-speech` (optional cloud TTS — tool `azure_tts`, same Speech key as `azure_stt`), `setup-api-key` |
| **Speech-to-text** | `speech-to-text` (whisper `transcriber` — default, offline), `azure-speech-to-text` (optional cloud STT — tool `azure_stt`, preferred when `AZURE_SPEECH_KEY` is set) |
| **Avatar / lip-sync** | `kling-official` |
| **Capture** | `playwright-recording` (browser flows), `ffmpeg` (post) |
| **Visualization** | `beautiful-mermaid`, `d3-viz`, `manim-composer`, `manimce-best-practices`, `manimgl-best-practices` |
| **Media editing** | `video-edit`, `video-download`, `video-understand`, `video-toolkit`, `visual-style` |

**When in doubt, read the category's meta routing file first:**
- Picking an animation runtime? → `skills/meta/animation-runtime-selector.md` routes between Remotion primitives, GSAP plugins, framer-motion, Lottie, Manim, D3.
- Picking a screen-recording mode (real capture vs synthetic terminal)? → `pipeline_defs/screen-demo.yaml` + `skills/pipelines/screen-demo/idea-director.md`.

## Quick Lookup

| Question | Where to look |
|----------|---------------|
| What tools exist? | `tools/tool_registry.py` and `registry.support_envelope()` |
| What providers are available for a capability? | `registry.capability_catalog()` |
| What tools exist for a vendor? | `registry.provider_catalog()` |
| How does a tool actually work? | the tool's `usage_location` from the registry |
| How should this pipeline stage behave? | `skills/pipelines/<pipeline>/...` |
| What is the checkpoint/review policy? | `skills/meta/` |

## What Not To Do

- **Do not bypass the pipeline.** Never write ad-hoc scripts to call tools directly. All production goes through pipeline stages with director skills. See Rule Zero.
- **Do not call generation tools without reading their Layer 3 skill.** Check the tool's `agent_skills` field, read the referenced skill, then craft your prompts using that guidance.
- **Do not skip stage director skills.** Before executing any pipeline stage, read its director skill. The skill contains the quality bar, the workflow, and the review criteria.
- Do not use deleted legacy names such as `tts_cloud`, `tts_engine`, or `video_gen`.
- Do not hardcode provider names, API key names, or setup URLs. Read them from the registry's `install_instructions` and `dependencies` fields.
- Do not tell a restricted shared-installation user to add credentials manually, create a `.env`, or export a key. Surface the unavailable provider as an administrator setup request and continue only with centrally provisioned capabilities.
- Before offering a direct vendor credential, check the registry for an available wrapper through an already configured provider (for example, a partner model hosted by fal.ai).
- Do not begin asset generation before user approval on the production plan.
- Do not hide degraded paths. Record substitutions and blocked options explicitly.
- Do not present a single unavailable tool in isolation. Always show the full capability picture: "X of Y providers configured for this capability."
- Do not skip the Provider Menu at preflight. The user must see what they have AND what they could unlock.
- Do not change provider, model, or render path without telling the user first and getting approval when the change is material.
