---
name: ai-video-gen
description: |
  Sole entry point for video-production requests and generated video assets. Route every standalone video deliverable through an OpenMontage pipeline. Within an approved pipeline asset stage, use OpenMontage video_selector for provider discovery, ranking, cost evidence, and execution. Never select a provider directly or bypass production checkpoints.
---

# Unified video production and generation

This is the single video entry skill. It has two levels: OpenMontage owns the
production, and `video_selector` owns provider selection for generated assets
inside that production. Provider-specific skills may add prompting knowledge,
but they are not alternative entry points.

Work in `E:/project/OpenMontage`. For a standalone production request, read
`docs/CURRENT_PROJECT_STATE.md` and `AGENT_GUIDE.md` before doing production
work. The registry, selected pipeline manifest, stage directors, project
artifacts, and user approvals are authoritative.

## Route the deliverable before selecting a provider

Classify the requested deliverable semantically. Do not route by a short list of
keywords and do not assume that a short duration means a single asset.

### Complete production

A standalone request whose user-visible result is a finished video is a
production: an advertisement, promotional video, trailer, launch reel,
explainer, social clip, edited piece, or any other final video deliverable.

For complete production:

1. Select the best matching manifest from `pipeline_defs/` and explain the
   recommendation. If the production type is genuinely ambiguous, ask before
   locking it.
2. Run registry preflight and present the actual provider menu, composition
   runtimes, unavailable capability upgrades, and music options.
3. Follow the manifest stage by stage. Read each stage director before doing
   that stage and preserve its human approval gates.
4. Initialize the canonical project so `project.json` exists. Preserve the
   required `proposal_packet`, `scene_plan`, `asset_manifest`,
   `edit_decisions`, `render_report`, `final_review`, checkpoints, decision
   log, cost log, assets, and final render.
5. Use `video_selector` only when an approved assets-stage plan calls for a
   generated video asset.

Do not turn a complete production into a single generated clip plus improvised
subtitles, static cards, or an ad-hoc FFmpeg wrapper. FFmpeg, Remotion, or
HyperFrames may compose the production only when selected and approved through
the pipeline's proposal and edit contracts.

### Single generated asset

Use the direct selector route only when the current work is already inside an
approved pipeline assets stage and the asset has a project id, scene or asset
identity, output path, and approved production plan. A provider diagnostic may
also rank capabilities without generation, but it must not be presented as a
finished production.

If that pipeline context is absent, treat the request as a production and start
at the pipeline route. Do not create a project-shaped folder manually as a
substitute for `project.json`, checkpoints, and canonical artifacts.

## Cost and approval gate

No asset generation starts until the user can see what may be charged. Before
the first paid or credit-consuming call, present:

- selected tool, provider, model or provider variant, and why it fits;
- operation, duration, resolution or quality tier, number of assets, and
  whether the call is a sample or batch;
- evidenced unit price or credit use, the estimated total, and currency or
  credit unit;
- uncertainty as a range when the registry cannot provide an exact price;
- a budget ceiling covering this approved stage or batch;
- genuinely available lower-cost or local alternatives and their quality
  tradeoffs.

A missing estimate or reported `0` does not prove that an external account is
free. If a provider may consume subscription quota or credits but exposes no
reliable price, say that the amount is unknown and ask for a maximum call count
or credit budget instead of inventing a currency value.

Write the proposal checkpoint as `awaiting_human` and stop before asset
generation. Continue only after explicit approval identifies the provider or
approved selector route, scope, and budget ceiling. Do not call a paid
generation operation before this approval. Earlier permission for one sample
does not authorize another asset, retry, batch, provider switch, or higher-cost
setting unless the recorded approval policy explicitly covers it.

After approval, enforce the recorded ceiling. A rejected gate, exhausted
budget, unknown paid-provider result, or unauthorized fallback is a typed stop,
not permission to continue with a different provider or cheaper-looking
production path.

## Asset provider route

For an approved generated asset:

1. Discover the live registry and read `video_selector.get_info()`.
2. Call `video_selector` with `operation="rank"` and the real target operation.
   Ranking is read-only and must precede execution.
3. Confirm that the selected provider/model, cost evidence, and parameters are
   within the recorded approval.
4. Read every skill named by the selected tool's `agent_skills` before writing
   the prompt.
5. Call the same `video_selector` once for generation. Keep and poll the
   original provider task until a typed terminal result; do not resubmit merely
   because polling is slow.
6. Record provider/model, request or response identity, timing, cost/credit
   evidence, result status, and artifact integrity in the project artifacts and
   cost log.

```python
from tools.tool_registry import registry

registry.discover()
selector = registry.get("video_selector")
if selector is None:
    raise RuntimeError("video_selector is not registered")
info = selector.get_info()
```

## Request mapping inside the assets stage

- Text prompt only: `operation="text_to_video"`.
- One product or reference image: `operation="image_to_video"` with
  `reference_image_path` for a local attachment or `reference_image_url`.
- Multiple image, video, or audio references:
  `operation="reference_to_video"` with the corresponding reference fields.
- Editing an existing clip: `operation="video_edit"` with `video_path` or
  `video_url`.
- Preserve approved duration, aspect ratio, references, model, quality tier,
  and output intent. Always use a new project-owned output path.

When the user explicitly approves a provider, pass it as
`preferred_provider`; the selector still validates availability and task fit.
When no provider is approved, do not add one from memory. Do not silently fall
back to any paid provider, local renderer, still-image treatment, or stock
source.

## Result contract

- `success=True`, a verified local artifact, a project artifact record, and
  preserved cost evidence are required for an asset-stage success.
- Validate generated video with FFprobe and a full FFmpeg decode, then perform
  the pipeline's visual and audio review before accepting it.
- A typed provider failure, unavailable approved route, failed media
  validation, or exceeded budget is terminal for that attempt.
- A timeout while the provider task remains active means observe the same task
  when supported. It is not authorization to submit again.
- Report the selected provider and the real failure stage. Never expose API
  keys, cookies, signed URLs, or full provider responses.
