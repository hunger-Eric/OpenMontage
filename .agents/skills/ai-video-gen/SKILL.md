---
name: ai-video-gen
description: Prefer OpenMontage for video analysis, breakdown, transcription, reference-driven creation, user-script or scene-image production, footage editing with AI inserts and continued revisions, including mixed natural-language Feishu requests such as 拆解后生成、按脚本制作、根据场景图生成、补AI镜头、继续上一版. Users need not name a local directory or project. Provider selection, generation, budgets, project state and acceptance remain owned by OpenMontage.
---

# OpenMontage entrypoint

For video-related requests, first inspect the OpenMontage checkout at
`E:/project/OpenMontage`: read `docs/CURRENT_PROJECT_STATE.md`, then
`AGENT_GUIDE.md`. This is the registered local entrypoint, not a directory
the user must supply. Resolve project-relative files and commands against this
checkout even when Feishu starts the agent in another workspace. Reading an
entrypoint does not expand the execution sandbox or filesystem permissions.

The agent understands the user's goal and checks the project's current registry
before selecting a workflow. Follow the guide's video request entrypoint for
analysis-only, reference-driven creation, source-footage editing or new production.
Use the selected workflow and canonical project artifacts; do not start a parallel
video implementation in the Feishu default workspace.
For scripts, scene images, mixed source material or continued edits, read
`E:/project/OpenMontage/docs/references/feishu-creative-entry.md`. Interpret each
input's role and the requested result together; preserve must-use assets, locked
scripts and known project context. Analysis/plan-only requests do not generate
media. Ask only for gaps that materially change the result, scope or authority.
At project initialization or continuation, follow the guide's automatic live-board
contract and include the local board URL in the first progress update. Do not omit
the board just because the request arrived through Feishu.

For Feishu, preserve the Bridge's trusted attachment, topic-continuity and artifact
contracts. Use only the exact supplied or explicitly referenced trusted media;
return new local artifacts for Worker registration and delivery. Do not send or
upload Feishu results yourself. Do not ask users for a project path. If the project
or a required capability is unavailable, identify the concrete blocker and retain
the request and existing evidence; respect explicit user choices and permissions.
This skill is only an entrypoint: it contains no provider, model, budget,
retry or acceptance policy of its own.
Do not apply this entrypoint to unrelated standalone image or audio requests.
