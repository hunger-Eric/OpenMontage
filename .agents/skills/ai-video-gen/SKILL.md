---
name: ai-video-gen
description: Prefer OpenMontage for visual video plans, text-only product video copy, video analysis, breakdown, transcription, reference-driven creation, user-script or scene-image production, footage editing with AI inserts and continued revisions, including natural-language Feishu requests such as 写视频方案、写视频文案、拆解后生成、按脚本制作、根据场景图生成、补AI镜头、继续上一版. Users need not name a local directory or project. Provider selection, generation, budgets, project state and acceptance remain owned by OpenMontage.
---

# OpenMontage entrypoint

For video-related requests, first inspect the OpenMontage checkout at
`E:/project/OpenMontage`: read `docs/CURRENT_PROJECT_STATE.md`, then
`AGENT_GUIDE.md`. This is the registered local entrypoint, not a directory
the user must supply. Resolve project-relative files and commands against this
checkout even when Feishu starts the agent in another workspace. Reading an
entrypoint does not expand the execution sandbox or filesystem permissions.

Before drafting a proposal, read the project constraints and workflow documents
relevant to the request. For automatic video generation, resolve the effective
provider from the actual registry and configured preferences first; parameters
supplied by the agent to a selector are routing inputs, not evidence of an
explicit user-selected provider. Preserve explicit user or project locks and
report missing capabilities instead of silently substituting one.

The agent understands the user's goal and checks the project's current registry
before selecting a workflow. Follow the guide's video request entrypoint for
analysis-only, reference-driven creation, source-footage editing or new production.
Use the selected workflow and canonical project artifacts; do not start a parallel
video implementation in the Feishu default workspace.
For scripts, scene images, mixed source material or continued edits, read
`E:/project/OpenMontage/docs/references/feishu-creative-entry.md`. Interpret each
input's role and the requested result together; preserve must-use assets, locked
scripts and known project context. Video-copy requests ("视频文案") deliver
text only, without images or video; naming this skill does not expand that
scope. Analysis, explicitly text-only and initial-concept requests also do not
generate media. Ask only for gaps that materially change the result, scope or
authority.
For video-plan requests, including "我有个产品叫 X，帮我写一份视频方案" or
"使用 ai-video-gen 技能，我有个产品叫 X，帮我写一份视频方案", read
`E:/project/OpenMontage/docs/references/manual-video-handoff.md`. Prepare
the visual parts with the shared [platform-neutral visual planning flow](../../../docs/references/visual-video-planning.md): keep reusable identity,
product, scene and style references distinct from an optional composed key
image for the segment's starting composition or interaction state, then write
the motion prompt for what changes over time. Choose only the references the
segment needs; a key image or extra character views are conditional, not
mandatory.
Organize the plan by generation segment, with one necessary reference-image group and one
complete copyable prompt per segment. Keep short shot/action beats inside the
segment's prompt; do not automatically split each beat into a generation task.
Users need not list these outputs or name a manual workflow. Explicit text-only
limits take precedence. In Feishu, use the project's independent native Base
handoff described in [Feishu video-plan Base](../../../docs/references/feishu-video-plan-base.md):
create the overview, reference-asset and generation-segment tables, upload actual
reference images as attachment fields, and link each segment to its asset records,
image order and purpose, narration and complete prompt. In a local request, or
when the user explicitly asks for Word, use the existing self-contained fixed-layout
DOCX; when the user explicitly asks for Excel, use XLSX. Do not emit multiple
formats by default.
Only the DOCX route uses an overview, reference-asset image section and one vertical
block per segment with embedded reference images. Base uses asset attachments and
linked segment records. Both connect scene/actions, narration/dialogue, on-screen
text and complete copyable prompts. Prepare or reuse actual product, character and main-scene images
as needed, including animated characters; text descriptions and image placeholders
do not complete the required visual references. Design the necessary views and
details without fixing the image count. Reference-asset records, or the DOCX image
section, record image IDs, visual settings, purpose and related segments. Each
segment states its selected IDs, local image order and uses, with matching
references in its full prompt. Reuse accepted images across segments. Retain
originals in the project. For Feishu, the Base is the default plan handoff and its
link is returned through the existing topic result; do not send messages yourself.
If the Feishu API or permissions are unavailable, retain the planned content and
report the concrete error rather than silently falling back to a document. End the task before
calling a video provider. Later supplied videos use the existing continuation
path. Complete-video requests retain automatic
production.
The manual plan is platform-neutral: describe the composition and performance,
without selecting or requiring a video model, provider, account or MCP session.
Employees choose their own video-generation platform. Image preparation still
uses the existing selected image route.
At project initialization or continuation, follow the guide's automatic live-board
contract and include the local board URL in the first progress update. Do not omit
the board just because the request arrived through Feishu.

For Feishu, preserve the Bridge's trusted attachment, topic-continuity and artifact
contracts. Use only the exact supplied or explicitly referenced trusted media;
return new local artifacts for Worker registration and delivery. Video-sample approval
requests must include the validated sample video as an output artifact, even
when production is waiting for approval; a local-only link is insufficient.
Do not send Feishu messages or upload chat-delivery attachments yourself; return
them through Worker. The native plan's Base records and image attachments use only
the restricted Base tool described above. Do not ask users for a project path. If the project
or a required capability is unavailable, identify the concrete blocker and retain
the request and existing evidence; respect explicit user choices and permissions.
This skill is only an entrypoint: it contains no provider, model, budget,
retry or acceptance policy of its own.
Do not apply this entrypoint to unrelated standalone image or audio requests.
