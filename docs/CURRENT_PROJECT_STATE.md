# OpenMontage Current Project State

Updated: 2026-10-11

## 2026-10-11 Flow mode compatibility and informational costs

- Flow video configuration supports the normal composer and expanded/collapsed
  Agent panels. It verifies the video composer before proceeding and does not
  navigate to the header Tools gallery. Both video and Agent starting modes
  were verified on the real Flow UI through retained settings, without submission.
- Per user instruction, the default credit ceiling is now null in shared model
  defaults and local preferences. Costs are informational, with one brief notice;
  an authorized production needs no separate fee approval. Explicit user caps
  remain optional. The sibling Flow bridge supports authorization without a cap
  while preserving single-use expiry and submission acknowledgement.
- Duplicate/unknown attempts still require reconciliation. This change did not
  submit a paid generation or resume historical production runs.

## 2026-10-11 unified Flow material upload and chair case completion

- The sibling bridge now supports existing file inputs and native media-picker
  uploads, waits beyond uploading placeholders, selects filename/stem cards,
  and uses Add-to-prompt when required. It does not fall back from a stale
  explicit target or treat chooser acceptance as verified completion.
- OpenMontage requires `uploaded=true` and `verified=true` before generation.
  Authorized supplied references can acknowledge the per-upload rights notice;
  the persistent do-not-show option is preserved.
- Real UI validation completed image association for the chair production and
  MP4 upload/association in a separate validation project. WAV selection in the
  ordinary video material picker did not produce a usable associated asset;
  the bridge reported failure and did not submit generation. Raw audio upload
  through Flow Music's separate Add → Audio entry remains unverified.
- Per the user's new production request, the existing chair run resumed through
  the unified provider, retaining the reference, prompt, model and 10s/9:16 plan.
  Its temporary 360p monkeypatch and inherited cap were removed. One acknowledged
  720p Flow generation was downloaded and locally composed with the title.
- Current authority: `projects/chair-product-promo-97bb0188-20261010/` generation
  receipt, attempt record, semantic/visual review and compose checkpoint. Final:
  `renders/chair-product-final.mp4`. Native audio is preserved and technically
  checked; audio listening was not verified in this session.

## 2026-10-10 Gemini 3.8 TTS default, per-production voice

- This workstation retains `gemini_generate_content_tts` as its default TTS
  tool, now defaulting to `gemini-3.8-flash-tts` through `generateContent`, aligned
  with video-platform's active speech model and its 3.8 audio request shape.
- No voice is configured globally or locally. A non-empty production-selected
  voice is still required before any provider request; video-platform's fixed
  voice preference was deliberately not imported, per the user's instruction.
- The adapter reuses the existing private Google credential, a 600-second
  request timeout and 24 kHz PCM/WAV normalization. Explicit historical 3.1
  requests retain their original request schema; no automatic model fallback.
- No new speech generation was authorized as part of this integration.
- Verification: the actual TTS selector resolves `gemini_generate_content_tts`
  with `gemini-3.8-flash-tts`; the configured key's read-only model metadata
  request returned HTTP 200 and advertises `generateContent`. Focused TTS,
  routing and Flow regression checks passed 82 tests. This metadata check is
  not a completed speech generation or listening-acceptance claim.

## 2026-10-10 personal Google Flow video default

- The user switched this workstation's default video provider to `google_flow`
  in ignored `config.local.yaml`. Shared defaults remain portable `auto`.
- Local settings mirror video-platform `config/provider-profiles.json`'s
  `google-flow-scene`: the sibling `google-flow-mcp-v4` stdio bridge,
  `Omni 1.1 Flash` and the Flow homepage. The historical 10-credit ceiling was
  removed on 2026-10-11 at the user's request.
  Configuration alone does not authorize a generation or a model substitution.
- Video execution resolves an existing project or creates one from the homepage,
  verifies Tools-mode model, duration, aspect ratio, 720p and one-result settings,
  verifies typed text, then confirms credits and waits for submission acknowledgement.
  A durable output-owned attempt record blocks duplicate/unknown submissions.
- Login and provider selection can be checked without generation. No paid test
  was authorized for this synchronization; real generation speed is unverified.
- Verification: actual selector rank resolves `google_flow_mcp_video` and
  `Omni 1.1 Flash`; the configured browser session exposes a ready project entry
  without generation. Focused provider/routing checks passed 99 tests; the
  contract and Flow/configuration suite passed 1,262 tests with seven skips.

## 2026-10-10 upstream integration and portable production defaults

- Fork origin remains `hunger-Eric/OpenMontage`; its pre-integration main was
  `9a7e80c6fad3f993ef4f4217c49e78f76c12d9ad` (no new origin commits).
- Original upstream `calesthio/OpenMontage` was fetched to `upstream/main` at
  `9327439db69021ab4b0e2776729bf3b58fdb5a87`. Relative to common base
  `95e1c3d0ab93482159818560f6a8c8e866b9139f`, upstream adds 45 commits across
  96 files; the pre-integration local branch had 30 independent commits at
  `f6d2166c1ff2c6c7d61a9dd38f51591149077e2f`. The user authorized committing
  and pushing the resolved integration on 2026-10-10. The integration retains
  upstream/main as a merge parent; live Git refs are authoritative for the
  current local and remote commit identities.
- Upstream adds model/host/tool-aware routing, media contract catalogs, HeyGen
  Avatar V, new image/video/TTS adapters, unknown-price handling; fixes Remotion
  asset staging, theme keys/contrast and CJK captions, WAN temporal latents,
  long-video sampling, transport-error reporting and pipeline/playbook schemas.
  These describe integrated source, not live provider-access verification.
- Nine merge conflicts were resolved preserving project receipts, same-engine
  preview/finalization, transcript/provenance checks, and prior uncommitted edits.
  Pre-update exact files/hashes and patch remain in
  `.tmp/upstream-update-20261010-223614/`; tracked-edit stash
  `7817f3461f8bea3009d13ac2647889e2cabc327a` remains recoverable.
- Shared selectors now default to `auto`; personal provider preferences and
  configured exclusions load from ignored `config.local.yaml`. This workstation
  retains Codex-native images, Google Flow video and Gemini generateContent narration
  with restricted omitted-route requests. Grok/HeyGen adapters and vendor skills
  are restored as optional integrations, excluded here through configuration.
- `gemini_tts` is the upstream Interactions adapter;
  `gemini_generate_content_tts` preserves the existing generateContent adapter
  and its bounded recovery/audio normalization. Exact tool/model identities
  distinguish their contracts. Shared Remotion skills have portable references;
  applicable user/global instructions can still select a local official reader.
- Audio-style measurements are advisory by default. Project
  `edit_decisions.audio_review_policy` can explicitly enforce agreed thresholds.
  Objective integrity, transcript/provenance and duplicate-submission gates remain.
  Explainer revision/send-back limits are three; reaching a limit preserves and
  reports unresolved artifacts, never automatically passes them. No monetary cap
  or whole-production deadline was added.
- Validation: broad integration suite passed 1,411 tests, with seven skips and
  three expected failures; final routing checks passed 90 tests, composition
  session/vertical checks passed 58, and Remotion TypeScript `tsc --noEmit` passed.
  Initial wider-run failures were an absent Google SDK and an obsolete duplicated
  entrypoint-provider assertion. The new project `.venv` inherits existing base
  packages and installs Google GenAI 2.29.0 locally; requirements now match the
  new transport's minimum 2.25.0. No global Python packages were modified.
  Existing personal Remotion 4.0.532 pins are preserved; the merged nanoid
  override matches the existing newer 3.3.19 lock entry.
- Test logs: `.tmp/upstream-update-20261010-223614/integration-tests-venv.log`,
  `final-route-tests.log` and `composition-tests.log`. Provider transports are
  mocked or media are synthetic local fixtures. No new paid generation, live
  verification of newly added provider endpoints, or external delivery occurred.

## 2026-10-10 account-aware Agnes video selection

- Current policy: `AGENT_GUIDE.md`, Project-owned generation route. The user
  supersedes the permanent v2.0 rule: each new production checks the configured
  key's model catalog and plan/access evidence, then the executing agent selects
  a suitable eligible model within the authorized provider/plan/spending scope.
- Current key's live `/v1/models` response listed `agnes-video-2.5-flash` and
  `agnes-video-2.5`. Listing alone is not proof of access.
- On 2026-10-10, one authorized 4-second 720P text test per model found:
  Flash completed, downloaded and fully decoded (1280x720, 4.48 seconds);
  ordinary 2.5 was rejected at creation with HTTP 503 / `model_not_found`:
  no available channel for `agnes-video-2.5` under `TokenPlan`.
- Account-specific evidence (no credentials):
  `../.tmp/agnes-model-access-20261010-214707/results.json` and its adjacent
  request, creation, terminal-response and media files. These are diagnostic
  artifacts, not a completed governed production or a billing receipt.
- Implementation: `video_selector(operation="discover_models")` reads the
  current catalog without generation. The executing agent passes its exact
  selected `model`; omission never injects a fixed version. New submissions
  recheck listing. `agnes_video` has version-specific 2.5/Flash parameters and
  retains explicit legacy requests/recovery. Ordinary 2.5 new submissions need
  authorized `allow_paid_model=true`; failures never change model/provider.
  Unknown future contracts are listed as unsupported and stop before generation.
- Live updated-selector acceptance reused the completed Flash task without
  submitting another task. Discovery then returned only Flash; recovery downloaded
  the exact same bytes (matching SHA-256, 1280x720). Evidence beside the original
  test: `adapter-live-discovery.json` and `adapter-recovery-result.json`.
  No fresh generation through the updated adapter was run; new-submission
  contracts are covered by mocked API tests, not a new paid-call claim.
- Recheck on each new production; changed key, plan, endpoint, access response
  or task failure invalidates prior access assumptions. Preserve historical
  production and recovery identities; no per-production test-call requirement.

## Historical: 2026-10-05 user-fixed Agnes Video 2.0 default (superseded)

- Historical context only; the 2026-10-10 policy above replaces these rules.
  At that time, the user specified a project-wide `agnes-video-v2.0` route
  and required preserving it despite public lifecycle notices.
- The adapter declared `DEFAULT_MODEL = "agnes-video-v2.0"`.
- The call chain now uses the locked provider for cost/runtime estimates,
  exposes the selected model at rank preflight, and passes the fixed 2.0 model
  into the adapter. Conflicting model aliases and other-model recovery receipts
  are rejected before external calls; historical receipts remain unchanged.
  Focused selector/adapter checks pass with mocked submission and polling.
  No live generation or availability check ran.

## 2026-10-03 same-engine composition acceptance

- New explainer productions author one project-local source tree during asset
  preparation and edit against final-audio transcript timing. The default
  composition route is `video_compose`: `preflight` -> `preview` -> owner visual
  acceptance -> `finalize`; instructions live in the edit/compose directors.
- Governed renders validate schemas, file references, runtime agreement and
  narration/subtitle provenance before invoking the renderer. `script_path`
  is loaded consistently for both render and review.
- Preview runs the existing delivery gate and full decode. Finalization binds
  source, engine, parameters, media and video hashes plus actual owner visual
  acceptance, then copies the accepted bytes without another render. Changes
  require a new preview; historical output paths cannot be overwritten.
- Thirty focused checks passed. The same-input full thirty-second comparison
  measured 101.012 seconds for the prior render/repeated-review path versus
  85.136 seconds for the new automatic path (15.7% observed reduction). Both
  MP4 bytes and all 900 decoded frames match; accepted-preview finalization
  took 0.379 seconds with no second render. The twelve frame sheets were
  inspected and changed-timeline reuse was refused. Evidence and limits:
  [composition comparison](run-reports/2026-10-03-composition-preview-comparison.md).
  Model authoring time and end-to-end Feishu improvement remain unverified.
  No provider generation, historical run mutation or external delivery occurred.

## 2026-10-03 V47-V01 AI operations growth video

- Project `v47-v01-ai-ops-growth-20261002` completed a fresh local production
  with seven Agnes Video 2.0 office-motion clips, Gemini Mandarin narration,
  an Archive.org CC BY-SA music track, and a project-local Remotion atelier
  composition. The earlier Agnes 2.5 selection is superseded only for this
  project by the user's explicit 2.0 instruction.
- Final MP4: `projects/v47-v01-ai-ops-growth-20261002/renders/v47-v01-ai-ops-growth-30s-final.mp4`.
  It is 720x1280, 30 fps, 30.016 seconds, H.264/AAC, and SHA-256
  `45FC0DEF01290DF3F96356E97499D27542858CEBA09B9771F971EB5105D8026E`.
- The formal `video_compose` review passes container, sampled-frame, audio,
  delivery-promise, seven-asset semantic, transcript-derived subtitle, and
  transcript-to-script checks. A full FFmpeg decode and a twelve-frame contact
  sheet review also pass.
- Canonical receipts are `artifacts/asset_manifest.json`,
  `artifacts/edit_decisions.json`, `artifacts/render_report.json`, and
  `artifacts/final_review.json`. No Feishu upload, send, deployment, Git commit,
  or push was performed; external delivery remains Worker-owned.

## 2026-10-03 bounded multi-shot execution guidance

- `AGENT_GUIDE.md` now owns one mandatory fast path for long multi-shot
  generation: run-owned contract freeze, reference transport preflight, one
  first-shot route gate, receipt-first recovery, bounded continuation, batch
  normalization/review, receipt-derived manifests, and one official final
  `video_compose` render plus final review.
- The explainer asset director now freezes the working request/geometry after
  the first accepted shot, permits at most 2-3 concurrent independent provider
  tasks when the provider/account supports them, and preserves accepted sibling
  shots during leaf repair.
- The compose director no longer instructs production agents to enter through
  a low-level Remotion operation. Raw renderer commands remain explicit
  debugging surfaces only; production staging and runtime dispatch belong to
  `video_compose(operation="render")`.
- Checkpoint guidance now requires schema validation before write and preserves
  unknown cost/token facts as schema-valid unknowns rather than zero.
- This documentation correction changes no provider/model/adapter, schema,
  Bridge configuration, or runtime default. No live generation, render,
  deployment, delivery, or push was performed for this change.

## 2026-10-02 simplified production defaults

- Current user-selected route: Codex native `image_gen` images -> Agnes video
  with Google Gemini TTS narration -> OpenMontage composition and acceptance.
- `image_selector` defaults to native delegation; it never silently submits an
  Agnes image request. Python registry discovery cannot prove native tool access.
- Native image generation has been verified in the desktop session; access in
  the actual Feishu Worker remains unverified. If absent, report that boundary
  rather than replacing the requested image provider.
- Gemini TTS transport uses the video project's official endpoint, shared key
  source, environment proxy route and a 600-second connection/read timeout.
  Voice remains task-selected; no global speed/pitch/post-processing preset.
- HeyGen provider and dedicated skill copies are removed. Common narration and
  talking-head skills now refer to OpenMontage tools, preserving explicit Kling
  talking-head/lip-sync routes without an implicit HeyGen entry.
- Related adapter/selector checks: 123 passed, including a real local CONNECT
  proxy simulation. Three optional Google image-backend checks remain blocked
  by the local missing `google.genai` dependency; no full-suite pass is claimed.
- Existing Agnes image adapter/receipts remain available for explicit alternatives.
  No new live generation or deployment was performed for this default change.

## 2026-10-02 image and narration transient recovery

- Agnes image and Gemini narration adapters automatically retry known transient
  failures on the same provider/model; default three attempts with backoff and
  Retry-After. No separate retry-budget approval is required.
- Empty Gemini audio retries unless the response explicitly blocks content.
  Authentication/invalid-input failures and unknown generation submission outcomes
  do not automatically resubmit. Agnes image download resumes its original URL.
- Selector-entry simulations cover recovery, exhaustion, explicit one-call
  instructions, permanent failures and preserving original image receipts.
  No new live provider generation, Bridge deployment or Feishu delivery was run.

## 2026-10-02 project-owned Agnes image-to-video acceptance route

- Historical route sample: `agnes_image` was registered and both selectors
  defaulted to Agnes before the simplified route above replaced the image default.
  Unavailable default generation stops without a provider switch. Explicit
  alternate providers and auto selection remain supported.
- Codex native `image_gen` is retained as an explicit agent-native image route;
  availability must be checked in the actual session/Worker tool inventory.
- `ai-video-gen` is now only a project entrypoint. The globally installed entry
  is a junction to this project's `.agents/skills/ai-video-gen` directory.
- Local route acceptance evidence lives in
  `projects/agnes-route-acceptance-20261002/artifacts/`. One live image and one live video completed. Composition decoded successfully,
  but semantic acceptance failed (framing and background continuity); final
  review is `revise`. Agnes Video v2.0 is marked retired in current official docs.
  No model switch or extra generation was performed.
- No Bridge changes, deployment or Feishu delivery have been performed.


## 2026-09-28 Agnes local image-to-video bridge repair

- `agnes_video` now declares and accepts `reference_image_path`, so
  `video_selector` preserves the local file for the provider instead of forcing
  the generic FAL upload path.
- The Agnes adapter follows the provider client's local-media behavior by
  uploading a local reference image to one-hour ephemeral Litterbox storage,
  then submitting the returned HTTPS URL to the existing Agnes Video v2.0
  image-to-video contract.
- Focused provider and selector regression coverage passes. No live image
  upload or paid video generation was run during the repair; those external
  layers remain unverified.

## Current decision

- Decision: keep `AGENT_GUIDE.md` as the stable production contract and
  `PROJECT_CONTEXT.md` as the architecture/convention authority; use this file
  only as the compact current coordination entry.
- Relationship: 共存.
- Status: Google Flow MCP provider changes and their focused automated tests are
  consolidated in `main`; real Provider and complete pipeline availability
  remain separately runtime-verified concerns.
- Current checkout: `E:\project\OpenMontage`, branch `main`. Read the exact
  current commit with `git rev-parse HEAD` rather than copying a SHA here.

## Worktree boundary

- The previously separate Google Flow provider changes were explicitly placed
  in commit-and-push scope on 2026-09-27. Future dirty files remain user-owned:
  read current status and diff before editing, staging, or claiming completion.

## Current authority

- Current coordination and dirty-worktree boundary: this file
- Production routing, approvals, checkpoints, providers and pipeline behavior:
  `AGENT_GUIDE.md`
- Architecture and source-of-truth map: `PROJECT_CONTEXT.md`
- Runtime capabilities: the current `tools/tool_registry.py` registry output
- Pipeline behavior: `pipeline_defs/*.yaml` plus the selected stage director
- Run truth: `projects/<project-id>/` canonical artifacts, decision log,
  checkpoints, assets and renders
- Provider/model/runtime changes and paid generation remain explicit user gates.

## Next safe step

- For a new production request, run the guide's request routing, registry
  preflight, pipeline selection and approval gates; do not reuse the current
  dirty implementation as proof of provider capability.
- For Google Flow work, distinguish focused automated tests from a real browser
  subscription run; the latter still requires the explicit approval and credit
  gates in `AGENT_GUIDE.md`.

## Invalidation conditions

- HEAD, branch, registry capability, provider authentication, pipeline manifest,
  or the user's approved production path changes.

## Reusable production reference

- Decision: use the accepted GEO official-site v4 production as the default
  method reference for similar Chinese educational promotional shorts.
- Relationship: 完整替换; v4 supersedes v1-v3 as the current reference.
- Status: 已验收 locally; platform publication and moderation remain unverified.
- Current reference:
  `projects/geo-official-site-foundation/artifacts/reusable-promo-video-reference.md`
- Runtime evidence:
  `projects/geo-official-site-foundation/artifacts/final-review-v4.json`
- Invalidation: a later explicit user preference, changed provider/runtime
  capability, changed platform rules, or a newly accepted project baseline.

## 2026-08-27 reference-video execution archive

- Decision: publish the accepted GEO official-site v4 to Douyin main account
  (`fengc`) and Bilibili, then archive the full reference-led production flow.
- Relationship: 共存; this archive records the run and does not replace the
  reusable production reference above.
- Status: 实现完成/自动化通过; Douyin and Bilibili submitted, public
  visibility not verified because neither platform returned a remote ID/URL.
- Archive:
  `projects/geo-official-site-foundation/artifacts/2026-08-27-reference-video-project/execution-process.md`
- Prepared publication copy:
  `projects/geo-official-site-foundation/artifacts/2026-08-27-reference-video-project/publication-copy.json`
- Publication run: `external-geo-official-site-foundation-20260827` executed
  once from isolated clean production checkout
  `E:/project/视频平台-publication-20260827` without modifying the original
  dirty worktree.
- Result:
  `projects/geo-official-site-foundation/artifacts/2026-08-27-reference-video-project/publication-result.json`
- External effects: one Douyin main-account submission and one Bilibili
  submission, both `submitted_unverified`; Hermes 2026-08-27 video, portrait
  cover, landscape cover, and daily-note section archived with matching SHA.
