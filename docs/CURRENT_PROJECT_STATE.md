# OpenMontage Current Project State

Updated: 2026-09-28

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
