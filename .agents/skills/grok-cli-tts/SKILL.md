---
name: grok-cli-tts
description: Generate narration with the user's OAuth-backed Grok subscription through grok-cli. Use for OpenMontage TTS, voice samples, or final narration when Grok is the approved speech provider.
---

# Grok CLI TTS

Use `grok-cli tts` only through the registered OpenMontage provider. This keeps
authentication, project assets, error handling, and provider selection visible.

## Required workflow

1. Confirm the script text, language, voice, and output format before a paid call.
2. For a new voice or style, generate a short representative sample and wait for approval.
3. Put approved outputs under `projects/<project_id>/assets/audio/` and record them in the asset manifest.
4. Invoke `tts_selector` with `preferred_provider="grok"` and `allowed_providers=["grok"]` when Grok is required.
5. Listen to the result and verify intelligibility, pronunciation, pacing, and file duration before approving it.

## Provider contract

- Pass narration text exactly as approved. Do not rewrite, translate, summarize, or add delivery cues.
- Always pass an explicit OAuth path with `--auth-file`; never read or print the auth file.
- Use `--json`, `--text`, `--voice-id`, `--language`, `--output`, and `--output-format` for deterministic automation.
- Optional public flags are `--sample-rate`, `--bit-rate`, `--optimize-streaming-latency`, `--text-normalization`, `--model`, and `--timeout`.
- Treat `data.file_path`, `data.media_tag`, and `data.output_format` as the stable success fields.
- The command writes the audio file itself; accept success only when the requested project output exists.

Example command shape:

```powershell
grok-cli tts --json --auth-file <auth-file> --text <approved-text> --voice-id <voice> --language zh --output <project-output.mp3> --output-format mp3
```

## Recovery and stopping rules

- Follow structured `error.recovery_action` values.
- Automatically handle only `refresh_then_retry`, once.
- Stop on `login_then_retry` so an unattended pipeline never launches an interactive login.
- Stop on quota, billing, entitlement, or rate-limit errors and report the exact structured error.
- Never switch providers, voices, models, or text-normalization behavior silently.
- Every call consumes the user's subscription quota; announce it immediately before execution.
