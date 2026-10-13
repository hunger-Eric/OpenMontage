# Video provider extension

`video_selector` is the shared request surface for video generation. Scripts,
roles, and scene plans remain canonical artifacts; Codex translates an approved
plan into a common prompt/reference request using the selected skill. Concrete
provider adapters remain discoverable `BaseTool` implementations in the
registry. The selector freezes the selected tool, provider, and requested model
before a provider call and returns those identities alongside the adapter's own
native result data. It does not manufacture a common completion receipt: output
paths, provider status, task identities, cost, and receipts stay adapter-owned.

An existing adapter may optionally define:

```python
def prepare_video_request(self, inputs: dict[str, object]) -> dict[str, object]:
    ...
```

The selector calls this hook only for the selected concrete tool, immediately
before its generic local-image-to-FAL upload fallback and before `tool.execute`.
The hook receives an isolated copy and may add provider-specific aliases, such as
an `image_url` derived from an existing reference field. It maps parameters only
and must return a dict that preserves every supplied field and value. It cannot
add, remove, or change a model identity (`model`, `model_id`, `model_name`, or
`model_variant`), an explicit route (`preferred_tool`, `preferred_provider`,
`hosting_provider`, or `allowed_providers`), or an existing attempt identity
(`attempt_id`, `idempotency_key`, `external_task_id`, or `project_url`). It must
not select a provider, generate media, write receipts, or read configuration
secrets; provider credentials remain environment-backed inside that adapter.

Returning a non-dict, changing or removing an existing field, or raising stops
before `execute`. The selector returns a failure naming the already-selected
tool/provider/model, with no fallback or provider switch. Adapters without the
hook retain their previous request path exactly.

The current registry determines what is actually registered, which is distinct
from local configuration or generation acceptance. Google Flow is the existing
`google_flow_mcp_video` local-MCP/browser adapter. A new Google direct or Google
Omni API contract needs its own concrete adapter; the existing `veo_video`
adapter does not stand in for Omni. Registered Seedance routes are
`seedance_video`, `seedance_replicate`, and `seedance_ark`; registered Kling
routes are `kling_video` and `kling_official_video`. Those names describe
registry entries only, not configured credentials or verified generation paths.

Any new adapter must be a `BaseTool` with `capability = "video_generation"` so
registry discovery can expose it. It consumes the same frozen common request and
owns its own cost, status, output-path, and native receipt behavior. Adding that
adapter does not change the earlier canonical artifacts or introduce guessed
vendor parameters. If provider limits cannot support the approved request,
report the gap instead of silently changing its duration or dropping reference
assets. A concrete adapter must retain its native model in its receipt
or result data so the frozen selection can be verified; this hook validation is
request-integrity control, not a security sandbox.
