---
name: text-to-speech
description: Create and validate project narration through OpenMontage's TTS tools.
---

# Project narration

Read `AGENT_GUIDE.md > Project-owned generation route`. Use `tts_selector`
(default Google Gemini TTS) or an explicitly selected provider tool. Use the
registered tool schema and returned provider-specific skills; do not choose
another provider because this common skill is attached to multiple TTS tools.

Keep the approved narration verbatim. Select a voice for this production and
pass it explicitly; no global default voice, speed, pitch or post-processing
preset is imposed. For Gemini, the adapter owns official generateContent
transport, shared credential resolution, environment proxy routing, audio
extraction and local WAV validation. Never put credentials in prompts/artifacts.

Ordinary transient recovery is part of execution, without separate retry-budget
approval. Use the same provider/model and preserve input. Respect an explicit
user call limit. Recover original submitted tasks/results before a fresh request
when the submission outcome is unknown. Inspect retry evidence in the tool result.

Save narration inside the project and register provider/model, voice, path,
integrity hash and actual duration in the asset manifest. Verify audio decoding
and duration before using it for timing, subtitles and composition. Follow the
project's current acceptance policy for audio review. A provider response alone
does not prove accepted narration or a delivered video.
