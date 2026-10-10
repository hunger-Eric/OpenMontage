"""Explicit tool/host/model constraints shared by capability selectors."""

from __future__ import annotations


def filter_explicit_route(inputs, candidates):
    tool_name = inputs.get("preferred_tool")
    host = inputs.get("hosting_provider")
    model = inputs.get("model") or inputs.get("model_id") or inputs.get("model_name")
    selected = []
    for tool in candidates:
        if tool_name and tool.name != tool_name:
            continue
        if host and getattr(tool, "hosting_provider", tool.provider) != host:
            continue
        if model:
            props = tool.input_schema.get("properties", {})
            models = set()
            for field in ("model", "model_id", "model_name"):
                models.update(props.get(field, {}).get("enum", []))
                if props.get(field, {}).get("const"):
                    models.add(props[field]["const"])
            models.update(getattr(tool, "supports", {}).get("usage_conditions", {}).get("supported_models", []))
            models.update(getattr(tool, "_MODELS", {}))
            models.update(getattr(tool, "_MODEL_ALIASES", {}))
            models.update(tool.get_info().get("model_catalog", {}))
            if model not in models:
                continue
        operation = inputs.get("generation_mode") or inputs.get("operation")
        routes = getattr(tool, "routes", None) or getattr(tool, "models", None)
        if isinstance(routes, dict) and operation and operation != "rank":
            model_routes = (
                routes.get(model, {}) if model else next(iter(routes.values()), {})
            )
            normalized = (
                "text_to_video"
                if operation == "generate" and tool.capability == "video_generation"
                else operation
            )
            if normalized not in model_routes:
                continue
        if tool.capability == "image_generation":
            props = tool.input_schema.get("properties", {})
            if any(inputs.get(k) and k not in props for k in ("mask_path", "mask_url")):
                continue
            if any(
                inputs.get(k) and k not in props and "images" not in props
                for k in ("image_path", "image_paths", "image_url", "image_urls")
            ):
                continue
            if operation == "precise_edit" and not (
                getattr(tool, "supports", {}).get("precise_edit")
                or isinstance(routes, dict)
                and any("precise_edit" in r for r in routes.values())
            ):
                continue
        selected.append(tool)
    return selected


def apply_provider_preferences(inputs, capability):
    """Use configured preferences only when the caller has not selected a route.

    Explicit request constraints keep their original meaning. Selection happens
    once before submission; execution failures never trigger another provider.
    """
    from lib.config_model import OpenMontageConfig

    config = OpenMontageConfig.load().providers
    result = dict(inputs)
    explicit = any(inputs.get(key) for key in (
        "preferred_provider", "preferred_tool", "hosting_provider",
        "model", "model_id", "model_name", "workflow_json", "workflow_path",
    ))
    if not explicit:
        provider = getattr(config, capability + "_provider")
        result["preferred_provider"] = provider
        if capability == "tts" and config.tts_tool:
            result["preferred_tool"] = config.tts_tool
        if config.restrict_to_preferences and provider != "auto":
            existing = result.get("allowed_providers")
            result["allowed_providers"] = ([provider] if not existing else
                [p for p in existing if p == provider])
            # An empty intersection must never mean an unrestricted route.
            if existing and not result["allowed_providers"]:
                result["allowed_providers"] = ["__no_authorized_provider__"]
    return result


def enabled_candidates(candidates):
    from lib.config_model import OpenMontageConfig

    disabled = set(OpenMontageConfig.load().providers.disabled_providers)
    return [tool for tool in candidates if tool.provider not in disabled]
