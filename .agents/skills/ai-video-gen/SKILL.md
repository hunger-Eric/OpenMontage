---
name: ai-video-gen
description: |
  Sole entry point for generic AI video generation and provider selection. Use for text-to-video, image-to-video, product clips, and choosing among Agnes, VEO, Kling, Sora, Runway, Seedance, MiniMax, HeyGen, Google Flow, Gemini Omni, local, and stock providers. Always call OpenMontage `video_selector`; never choose or call a provider directly unless the user explicitly requests a provider-specific operation that the selector cannot represent.
---

# Unified AI video generation

All generic video-generation requests go through OpenMontage's `video_selector`.
Do not preselect Google Flow, Agnes, HeyGen, or another provider from memory, from
an environment variable, or from a provider-specific skill. The runtime registry
and selector are authoritative.

## One route

1. Work in `E:/project/OpenMontage` and discover the current registry.
2. Read `video_selector.get_info()` for its live status and input schema.
3. Call `video_selector` with `operation="rank"` and the real target operation to
   inspect viable providers without starting a generation.
4. If the chosen route consumes credits or requires provider-specific approval,
   obtain the missing explicit authorization before generation. Never infer a
   budget, project URL, provider, or permission.
5. Call the same `video_selector` once for generation. Keep and poll that original
   provider task until it reaches a typed terminal result; do not resubmit because
   polling is slow.
6. Return only an artifact from a successful `ToolResult`. Validate the local
   video with FFprobe and a full FFmpeg decode before claiming completion.

```python
from tools.tool_registry import registry

registry.discover()
selector = registry.get("video_selector")
if selector is None:
    raise RuntimeError("video_selector is not registered")

info = selector.get_info()
```

## Request mapping

- Text prompt only: `operation="text_to_video"`.
- One product/reference image: `operation="image_to_video"` and
  `reference_image_path` (preferred for a local attachment) or
  `reference_image_url`.
- Multiple image/video/audio references: `operation="reference_to_video"` and
  the corresponding `reference_*_paths` or `reference_*_urls` fields.
- Editing an existing clip: `operation="video_edit"` with `video_path` or
  `video_url`.
- Preserve the user's duration, aspect ratio, references, and output intent.
  Use `output_path` for the new `.mp4`; never overwrite an accepted artifact.

When the user explicitly names a provider, pass it as `preferred_provider` and
let the selector validate availability and task fit. When no provider is named,
do not add one: the selector owns the default and must fail closed if that
default is unavailable. Do not silently fall back to Google Flow or any other
paid provider.

## Result contract

- `success=True` plus a verified local artifact is completion.
- A typed provider failure, rejected payment gate, unavailable default, or
  failed media validation is a terminal failure for that attempt.
- A timeout while the provider task is still active means continue observing
  the same task when supported; it is not permission to create another task.
- Report the selected provider and failure stage from the real result. Do not
  turn provider failure into `WAITING_INPUT` unless the result explicitly
  identifies missing user input that can make the same request executable.
- Never expose API keys, cookies, signed URLs, or full provider responses.
