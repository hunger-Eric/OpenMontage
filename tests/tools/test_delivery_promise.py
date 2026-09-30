from lib.delivery_promise import DeliveryPromise, PromiseType, classify_from_brief


def test_classify_from_brief_source_led_reclassification_clears_motion_requirement() -> None:
    promise = classify_from_brief("talking-head", {"has_footage": True})

    assert promise.promise_type == PromiseType.SOURCE_LED
    assert promise.source_required is True
    assert promise.motion_required is False


def test_classify_from_brief_explicit_motion_override_survives_reclassification() -> None:
    promise = classify_from_brief(
        "talking-head",
        {"has_footage": True, "motion_required": True},
    )

    assert promise.promise_type == PromiseType.SOURCE_LED
    assert promise.motion_required is True


def test_classify_from_brief_avatar_defaults_stay_motion_required_without_footage() -> None:
    promise = classify_from_brief("talking-head", {})

    assert promise.promise_type == PromiseType.AVATAR_PRESENTER
    assert promise.motion_required is True


def test_delivery_promise_resolves_asset_ids_from_manifest_as_real_motion() -> None:
    promise = DeliveryPromise(
        promise_type=PromiseType.MOTION_LED,
        motion_required=True,
        source_required=False,
        tone_mode="cinematic",
        quality_floor="presentable",
    )

    result = promise.validate_cuts(
        [{"id": "c1", "source": "clip-01", "in_seconds": 0, "out_seconds": 5}],
        asset_manifest={
            "version": "1.0",
            "assets": [
                {"id": "clip-01", "type": "video", "path": "assets/video/clip-01.mp4"}
            ],
        },
    )

    assert result["valid"] is True
    assert result["motion_ratio"] == 1.0
