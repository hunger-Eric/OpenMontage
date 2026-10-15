# Video Reference Analyst — Meta Skill

## When to Use

When the user provides a video URL (YouTube, Shorts, Instagram, TikTok, or any URL)
or a local video file as a REFERENCE — meaning "make me something like this," not
"edit this footage."

If the user says "edit this video" or "cut this into clips," route to the appropriate
footage-led pipeline (clip-factory, talking-head, hybrid) instead. This skill is for
REFERENCE-based production.

## Detection Signals

Trigger this skill when:
- User pastes a YouTube/Shorts/Instagram/TikTok URL
- User says "something like this," "inspired by," "in this style," "similar to"
- User uploads a video and says "I want one like this"
- User says "I saw this video and want to make something like it"

Do NOT trigger when:
- User provides footage and says "edit this" or "cut this" → use source_media_review
- User provides audio and says "make a video for this" → standard pipeline
- User just wants a transcript → use TranscriptFetcher directly

## Protocol

Read `skills/meta/reference-production-handoff.md` for the shared evidence,
adaptation and downstream-review contract. Reference interpretation follows the
original migrated Hypit method linked below; existing structured fields project
that connected reading for downstream consumers.

### Step 1: Analyze the Reference

#### Reference acquisition and evidence gate

Resolve the media before interpreting it:

- For any Douyin page-shaped URL containing `modal_id=<id>`, normalize the source
  to `https://www.douyin.com/video/<id>` before download. Canonical `/video/<id>`
  URLs pass through unchanged; unknown shapes are tested by the extractor rather
  than guessed to be authentication failures.
- `video_downloader` automatically reuses the primary uploader state at
  `~/.social-auto-upload/runtime/cookies/douyin_<local-user>.json` for Douyin only.
  `playwright_storage_state_path` is an explicit override, not a required caller
  argument. Never print cookie names or values, copy them into logs, or create a
  second plaintext cookie file. If no verified authorized state exists, ask the user
  to provide a video file or refresh the existing uploader login state.
- A metadata-endpoint `Fresh cookies` warning is not a final cookie verdict.
  The user-approved repair provides `reference_acquisition: "auto"` as the normal
  downloader/analyzer path: a generic `Fresh cookies` or unexpected-webpage extractor
  failure resolves the normalized source once in an isolated headless browser,
  then downloads its media address with yt-dlp. `extractor` explicitly disables
  recovery; `browser` selects normal browser acquisition directly. This is local
  OpenMontage transport, not an invocation of Kedou or another external parser.
  Generic failures are not replayed through the same page extractor before recovery.
  Existing authorized uploader cookies are scoped to the source host, read in memory,
  and never persisted or sent to a third-party parsing service.
  `Fresh cookies` alone is `EXTRACTOR_BLOCKED`, not evidence of an expired login.
  HTTP 403 is `ACCESS_DENIED`; verification challenges are `CHALLENGE_REQUIRED`.
  Stop on these blocks without retrying or asking for a cookie refresh as a cure.
- Do not treat the outer `ToolResult.success` flag as proof that analysis succeeded.
  Require a downloaded media file, positive duration, representative keyframes, and
  relevant entries in `_analysis_meta.steps_completed`. Empty default fields, zero
  scenes, or a `download:` entry in `steps_failed` are not analysis evidence.
- Metadata extraction and media download can diverge. If metadata fails but the media
  file is present and `ffprobe` plus keyframe/scene outputs validate it, continue the
  visual analysis and label title/uploader metadata as partial rather than discarding
  the successful media evidence.
- Treat URL resolution and authentication as separate states. A canonical supported
  URL passes through unchanged; a known page-shaped alias such as any Douyin URL with
  a valid `modal_id` resolves to `/video/<id>`; an unknown shape is passed to the
  extractor and is unsupported only when the extractor returns `UNSUPPORTED_URL`.
  Never report `UNSUPPORTED_URL` as expired cookies.
- Never open a headed browser, auto-play the page, inspect browser network traffic,
  or trigger QR login as an automatic download fallback. Explicit login rejection
  after the normalized URL was attempted with the authorized storage state is
  `AUTH_REQUIRED`; preserve the task and request refresh of that existing state.
  Retain `storage_state_source` and the classified failure in the analysis brief;
  a generic parser cookie warning must never be described as an account failure.
- Apply failure classification across platforms. YouTube's `not a bot` rejection
  is `CHALLENGE_REQUIRED`, not proof of an expired session. A message listing
  unavailable content, rate limits, **or** login is `EXTRACTOR_BLOCKED` until
  another observation establishes the cause. TLS fingerprint rejection and HTTP
  412 are `ACCESS_DENIED`; HTTP 429 is `RATE_LIMITED`. Do not replay these failures
  as another media or caption request. Do not downgrade HTTPS or bypass challenges.
- `REFERENCE_UNAVAILABLE`, `MEDIA_PROTECTED`, and `GEO_RESTRICTED` need an
  accessible reference or authorized local original, not a cookie-refresh loop.
  `NETWORK_UNAVAILABLE` requires checking the actual failed host/network route.
- A browser playback result, preview, or `blob:` player is not a downloaded video.
  Require a nonempty local file with valid video streams and positive duration.
  A missing file is `REFERENCE_MEDIA_UNAVAILABLE`; invalid bytes are
  `INVALID_REFERENCE_MEDIA`. Label transcript-only work unsuccessful when no
  transcript text was obtained. A file materially shorter than known source
  duration is `INCOMPLETE_REFERENCE_MEDIA`, not a complete-reference acquisition.
  The isolated recovery requires a single playable video, finite duration, and a
  direct HTTP(S) media address or a single observed HLS/DASH manifest. Ambiguous
  segmented sources stop as `SEGMENTED_MEDIA_UNRESOLVED`; do not guess among streams.
  Downloads go into fresh acquisition directories, must match the observed duration,
  and must pass full decoding. Record safe acquisition stages and receipts; never
  emit signed media URLs or session headers. No headed login, QR interaction,
  CAPTCHA solving, software installation, provider swap or fee is authorized by
  this path. Explicit access/auth/challenge/limit failures stop.

### Use the migrated Hypit reference-understanding method

Read the original skill's
[Understand and adapt](../../third_party/hypit/SKILL.md#understand-and-adapt)
with its account of objects and relationships over time.
Read the unchanged upstream
[Understanding a reference video](../../third_party/hypit/references/creation/reference-video.md).
It is the method for this step, not a summary of it. For generated footage and
camera/action relationships, also read the original
[Video direction](../../third_party/hypit/references/playbooks/craft/video-direction.md).
The local source and its provenance are described in
[the migration mapping](../../docs/references/hypit-reference-port.md).
Existing acquisition, provider, approval and composition contracts remain owned
by OpenMontage; the imported reference book does not select a new Runtime,
account, model or generation service.

`video_analyzer` standard/deep now executes the migrated inspection source for
probe, paged grids and visual-change candidates. It also retains its existing
structural measurements for compatibility. No installed Hypit command or package
is used. Begin in a fresh analysis directory:

```python
video_analyzer.execute({
    "source": "<url or path>",
    "analysis_depth": "standard",
    "output_dir": "<project>/analysis/<reference-revision>"
})
```

The original compact grid defaults are an initial view. Follow the original
method's whole/detail investigation: use the registered `reference_media` with
`operation=tile|tiles|frames|cut|boundaries|probe`, choosing original `options`
(`start/end`, `every`, `cell`, `at`, `around`, `transcript`, `ranges`, etc.) as the
question requires. Native results preserve requested and actual frame times.
For this trial, dense half-second pages and 12 Hz boundary candidates were useful;
those numbers are not a mandatory policy for every video. Movement can need a
closer range and larger cells; words and persistent visual systems can need a
wider view. A candidate or an overview is not a semantic interpretation.

As upstream specifies, retain the connected account in the analysis directory:

- `ANALYSIS.md`: the whole-piece explanation and recurring systems, including how
  concrete audiovisual choices serve the viewer and the intended adaptation.
- `TIMELINE.md`: source-time-locatable behavior and meaning: exact text/appearance,
  entry, movement, persistence, exit and the words/actions each responds to.
  Sections may overlap; a system can outlive a camera cut.
- `PROGRESS.md`: unresolved source-time questions and the next useful inspection.

These are the original Hypit note roles, not a new shot-schema or approval gate.
`video_analysis_brief.reference_understanding` links their paths and source-bound
execution receipts; the tool leaves reading pending. Author the notes from the
actual media. Project fields such as content/style/scene summaries are projections
of that reading for existing consumers; their schema validity and automatic scene
count never prove that the reading occurred. Reopen source intervals when a detail
conflicts instead of compressing away actions, camera changes or graphic timing.

Use the existing transcription path for spoken material and preserve actual word
times when available. The migrated grid reader accepts the original
`hypit.transcript@1` shape; segment times must not be invented as word alignment.
Missing timings stay missing, as in the original source. Frames and transcripts
cannot establish music quality, voice timbre or lip sync without suitable audio
and temporal observation. Keep those limits explicit.

The original camera guidance carries forward: a motion name is a starting point;
inspect its path, scale, pace and neighboring events when distinctive. Record the
observed behavior before deciding target implementation. When an exact action or
camera path is defining, upstream recommends keeping a useful source excerpt as
motion evidence and binding that actual material to a supported generation input.
A keyframe or an excerpt mentioned only in prose does not carry that movement.
Don't reduce the source reading to one repeated fixed-camera prompt.

Give the user the current interpretation and concrete discoveries, with useful
frames or word-labeled grids, while the reading develops. Preserve uncertainty
and update the notes when evidence changes the interpretation. Continue through
the existing production stages from this connected account.

### Step 2: Capability Audit

Run standard preflight:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
```

Map the reference video's requirements against available capabilities:

```
REFERENCE NEEDS          YOUR CAPABILITIES          GAP
─────────────────────    ─────────────────────      ──────────
Video clips (sci-fi)     Video gen: 0/12 configured BLOCKED without key
Narration (deep male)    TTS: ElevenLabs available  READY
Background music         Music: MusicGen available  READY
Composition engine       Remotion: available        READY
Post-production          FFmpeg: available          READY (standalone ops)
```

**Composition engine selection:** For a new production, check Remotion
availability and record `render_runtime: "remotion"`; do not expose a technical
runtime menu or require a second confirmation. Preserve an explicit historical
runtime. HyperFrames requires an existing explicit lock or an explicit user
request for that runtime; a specialized brief alone does not authorize it.
FFmpeg remains reserved for standalone editing, audio, subtitle, and packaging
operations. If Remotion is unavailable, report the gap and do not silently
substitute a renderer.

Be honest about gaps. If video generation is needed but unavailable, say so clearly:

```
"This reference uses generated sci-fi footage. Right now you don't have any video
generation providers configured. Here are your options:

• Add the gateway or provider key recommended by `provider_menu()` for video generation
• If multiple provider options are available, summarize the tradeoffs and recommend one based on the user's brief
• Proceed without video gen → I'll use stock footage + Remotion animations instead
  (different feel, but still works)

Which would you prefer?"
```

Read install_instructions from the registry for each unavailable tool — do NOT
hardcode key names, provider names, or setup URLs.

### Step 3: Ask Critical Questions

Before proposing, gather what the VideoAnalysisBrief doesn't tell you:

1. "Do you want narration in your version, or visuals-only with music?"
2. **If narration: lock the audio architecture now.** Ask:
   "How should the story be told? Options:
   • **Single narrator** — one voice tells the whole story (like a Pixar short)
   • **Character dialogue** — characters speak to each other, no narrator
   • **Narrator + character voices** — narrator drives the story, characters
     have occasional dialogue lines"
   This decision shapes the script, voice casting, and budget. It MUST be
   resolved before proposals — do not defer it to the script or compose stage.
3. "How long should your video be? The reference is [X] seconds."
4. "Is there a specific topic/subject you want, or should I riff on the
   same theme as the reference?"
5. "Any elements from the reference you specifically love or hate?"

Do NOT ask all at once. Lead with the most important gap. If the user's initial
message already answers some of these, skip those.

### Step 3b: Lightweight Research

**This step is mandatory.** Even with a clear reference video and user direction,
the agent must do targeted research before proposing concepts. Do NOT skip this
and rely solely on the reference analysis + your own knowledge.

Research scope (keep it focused — this is not the full research-director stage):

1. **Content landscape:** Search for 3-5 existing videos similar to what the user
   wants. What works? What's been overdone? What angles are fresh? This grounds
   your proposals in what's actually out there, not just what you imagine.

2. **Style/technique research:** Search for best practices relevant to the
   production approach:
   - If AI video gen: which models handle this subject best? Known prompting
     patterns? Character consistency techniques?
   - If animation: what animation styles suit this content?
   - If the reference has a distinctive technique: how is it achieved?

3. **Subject-matter research:** If the user's topic has factual content (science,
   history, how-things-work), gather 3-5 specific data points or facts that could
   make the video more interesting. Even for entertainment/comedy videos, research
   what makes similar content engaging (tropes, hooks, payoff patterns).

**How to present:** Don't dump raw research. Weave findings into your proposals:
- "I looked at similar channels — most food personification videos use X, so our
  twist of Y would stand out"
- "Kling handles anthropomorphic characters well when you use [specific technique]"
- "The top-performing 60-second comedy shorts all use a 3-beat structure: setup,
  escalation, unexpected payoff"

**Time budget:** 2-3 minutes of web search. This is a lightweight pass, not a
deep investigation. The full research-director stage runs later inside the
pipeline if needed.

### Step 4: Creative Proposals (2-3 variants)

First retain the user's intent in `metadata.reference_adaptation.mode`.
“复刻”/“复制” alone does not select a strict copy. Borrowing rhythm, voice character,
composition or the explanation format uses `creative_adaptation`, with those
specific dimensions retained and content adapted to the user's goal. This mode
does not require changing the very style the user wants to borrow or proposing
unrelated concepts. Use `faithful_replica` only for an explicit request to retain
source content/order/timing and authorized layers. Do not require generic new
copy or a provider/runtime change. Apply differentiation below only to dimensions
the user wants changed. Ask only about material unresolved intent.
Follow `reference-production-handoff.md` for the executable replica contract.

Use this structure for each variant:

```
## Option [A/B/C]: "[Title]"

**Inspired by:** [what it keeps from the reference — pacing, structure, tone]
**Creative twist:** [what it changes — angle, subject, visual treatment, hook]

**Visual plan:**
- Playbook: [closest match + customizations]
- Visual treatment: [how visuals will be created — which tools, which providers]
- Composition: [Remotion by default after availability check; preserve an
  explicit historical or user-requested HyperFrames path, if applicable]
- Motion: [video gen clips / Remotion spring animations on stills / etc.]
- Clip duration strategy: [fit the live provider envelope to narrative beats,
  speech and action windows. Consolidate adjacent scenes only when the story
  and continuity benefit; longer clips do not inherently mean smoother editing.
  Final cut lengths come from the actual accepted media, not equal clip slots.]

**Audio plan:**
- Audio architecture: [single narrator / character dialogue / narrator + characters]
- Voice casting: [voice name + ID for each role — narrator, character A, etc.]
- Speech route: [use the approved native speech, TTS, supplied audio or silent
  architecture. Discover current tools and provider contracts; do not hardcode
  a TTS default or add TTS to a video-native speech plan. Explain continuity
  limits and bind the representative sample to this same architecture.]
- Music: [library track / generated / none]
- Sound design: [any special audio needs]

**Duration:** [X seconds]
**Estimated cost per provider option:**
Present a provider comparison table so the user can choose:
```
Provider        Quality    Speed      Cost (N clips)    Total
─────────      ────────   ─────      ──────────────    ─────
VEO 3.1        Highest    Slow       $X.XX             $X.XX
Kling Pro      High       Medium     $X.XX             $X.XX
Sora V2        High       Medium     $X.XX             $X.XX
LTX Distilled  Lower      Fastest    $X.XX             $X.XX
```
+ Image generation: $X.XX (N images × $X.XX each via [provider])
+ TTS narration: $X.XX (N words via [provider])
+ Music: $X.XX ([source])

**Do NOT pick the provider for the user.** Present the options with
costs, recommend one with a brief reason, and let them decide.

**Honest assessment:** [What this will look like realistically — don't oversell]

**Layer 3 skills:** [List the agent_skills from each tool that will be used.
  These MUST be read before writing any generation prompts. E.g.:
  - Video gen: `ai-video-gen` skill for provider-specific prompt patterns
  - Image gen: `flux-best-practices` for FLUX prompt engineering
  - TTS: `elevenlabs` or `openai-docs` for voice tuning
  Skipping Layer 3 skills is a governance violation.]
```

**Differentiation patterns:**

| Pattern | Example |
|---------|---------|
| **Same structure, different subject** | Reference: "How black holes work" → Ours: "How neutron stars work" with same pacing |
| **Same subject, different angle** | Reference: "Kubernetes explained" → Ours: "Kubernetes from a security engineer's POV" |
| **Same tone, different visual treatment** | Reference: stock footage + voiceover → Ours: animated motion graphics + voiceover |
| **Same content, different platform** | Reference: 10-min YouTube → Ours: 60-sec Shorts version with faster pacing |
| **Counter-take** | Reference: "Why AI will replace jobs" → Ours: "Why AI won't replace YOUR job" |

**Cost transparency is mandatory.** Each concept must include:
- Itemized cost estimate at the user's requested duration
- Cost broken down by: image gen, video gen, TTS, music, total
- Provider names for each cost line
- Honest note about what the budget buys vs. doesn't buy

**Recommendation:** Always recommend one option with a brief reason why. Don't leave
the user paralyzed with equal choices.

### Step 4b: Layer 3 Skill Gate (MANDATORY)

**Before ANY asset generation** (sample or full production), the agent MUST:

1. Read the **Layer 2 skill** for each tool from `skills/` directory (usage guidance, input schemas, best practices)
2. Check the `agent_skills` field on every tool that will be used
3. Read each referenced **Layer 3 skill** in `.agents/skills/` (provider-specific prompting)
4. Apply the provider-specific prompting guidance to all generation prompts

**NEVER read tool source code (*.py) to understand how to use a tool.**
Skills exist precisely so the agent doesn't need to read implementation code.
Layer 2 skills describe *what* and *when*. Layer 3 skills describe *how*.

This is NOT optional. The AGENT_GUIDE says: *"Layer 3 is not optional.
Every generation tool has an agent_skills field. Read them before writing
prompts."*

Example checklist before generating:
```
Tool              agent_skills              Read?
────────────      ────────────────────      ─────
video_selector    ai-video-gen              [ ]
flux_image        flux-best-practices       [ ]
elevenlabs_tts    elevenlabs, text-to-speech [ ]
video_compose     remotion-best-practices   [ ]
```

Do NOT proceed to Step 5 until all relevant Layer 3 skills are read.
The difference between a generic prompt and a skill-informed prompt is
the difference between "usable" and "cinematic."

### Step 5: Complete-plan confirmation

Enter the selected existing pipeline before generation. Execute research,
proposal, script and scene_plan, prepare necessary actual reference images,
then present the complete standalone plan board at the scene_plan human gate.
Do not generate a ten-second sample or request a separate sample approval.

### Step 6: Continue the same pipeline

After that exact plan revision is approved for automatic production, generate
the complete planned film and continue internal review and post-production.
Manual production resumes with trusted returned clips in the same project.
Plan-only delivery stops without video generation. Preserve references,
script and continuity; do not invent past stage completion or approval.

**Mandatory steps:**
1. Read the pipeline manifest: `pipeline_defs/animation.yaml` (or whichever
   pipeline matches the production type)
2. Execute **stage by stage** in order — research → proposal → script →
   scene_plan → assets → edit → compose → publish
3. Before EACH stage, read its director skill from
   `skills/pipelines/<pipeline>/<stage>-director.md`
4. Produce the required artifacts at each stage
5. Hit every checkpoint where `checkpoint_required: true`
6. Get user approval where `human_approval_default: true`

**Do NOT collapse stages.** Do not jump from "user approved proposal" to
"generate all assets." The pipeline stages exist to enforce quality gates,
artifact dependencies, and review checkpoints. Skipping them is a governance
violation.

**Context to carry into the pipeline:**
- VideoAnalysisBrief as grounding context in the research/proposal stage
- User's chosen variant as the approved direction
- Complete-plan feedback incorporated into the approved scene-plan revision
- All creative differentiation decisions recorded in the decision_log
- Audio architecture and voice casting decisions from Step 3
- Layer 3 skills already read from Step 4b

The pipeline takes over from here. The VideoAnalysisBrief travels alongside the
standard artifacts, providing reference grounding at every stage.

The canonical adaptation plan and its downstream revision references follow
`reference-production-handoff.md`; merely retaining the analysis file alongside
the project is not evidence that a stage consumed it.

## Multiple Reference Videos

When the user provides multiple reference URLs:

1. Analyze each video separately (run VideoAnalyzer on each)
2. Present a comparative summary: "Video A does X well, Video B does Y well"
3. In proposals, note which elements are inspired by which reference
4. The VideoAnalysisBrief for the primary reference travels with the pipeline;
   secondary references are noted in the research_brief

## Error Handling

| Failure | Action |
|---------|--------|
| Known page-shaped URL | Resolve it to the canonical media URL and retry the same background acquisition |
| Extractor returns `UNSUPPORTED_URL` | Report an extractor/input-shape issue, never expired cookies |
| Authenticated background download returns `AUTH_REQUIRED` | Preserve the task and request refresh of the existing authorized state; never open a visible browser automatically |
| `EXTRACTOR_BLOCKED`, `ACCESS_DENIED`, or `CHALLENGE_REQUIRED` | Preserve the task and report the parser/access/challenge block with credential provenance; do not retry, bypass the block, or claim the uploader login expired |
| Other URL download failure | Report the classified error, suggest another URL or local file, and do not pretend the reference was analyzed |
| Music-only soundtrack | Skip STT; record `music_only` and treat `has_transcript: false` as expected |
| Speech present but no captions/transcript | Download video and use a configured local transcriber; report the boundary if unavailable |
| Scene detection fails | Fall back to uniform frame sampling |
| All analysis fails | Ask user to describe the reference video verbally, proceed with standard creative intake |

Never silently skip analysis steps. If something fails, tell the user what happened
and what the impact is on the analysis quality.
