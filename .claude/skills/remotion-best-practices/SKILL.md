---
name: remotion-best-practices
description: Official Remotion practices from the registered local source checkout
---

# Local official Remotion source

Read the complete canonical skill:

```powershell
python C:/Users/fengc/.codex/tools/remotion-source.py read --skill remotion-best-practices
```

Follow its references through the same reader using repository-relative paths. Source/API authority is the checkout in `C:/Users/fengc/.codex/remotion-source.json`; the old `rules/` copy is historical. Match APIs to the rendering project's lockfile with `--revision v<locked-version>`. This routing does not upgrade rendering dependencies or override OpenMontage's project-specific pipeline and approval rules.
