"""Runtime decisions remain valid without a user-facing engine menu.

The former prose tests forced every director to present two render engines.
New-work discovery and routing behavior are covered by runtime-policy tests;
this contract checks the actual canonical decision artifact, including history.
"""

from schemas.artifacts import validate_artifact


def _runtime_decision(options, selected):
    return {
        "version": "1.0",
        "project_id": "runtime-policy-test",
        "decisions": [{
            "decision_id": "runtime-1",
            "stage": "proposal",
            "category": "render_runtime_selection",
            "subject": "Composition runtime",
            "options_considered": options,
            "selected": selected,
            "reason": "Use the requested production policy or preserve the existing lock.",
        }],
    }


def test_single_remotion_choice_is_a_valid_canonical_decision():
    validate_artifact("decision_log", _runtime_decision([
        {"option_id": "remotion", "label": "Remotion", "score": 1.0,
         "reason": "Default runtime for new productions."},
    ], "remotion"))


def test_historical_runtime_shortlist_remains_a_valid_canonical_decision():
    validate_artifact("decision_log", _runtime_decision([
        {"option_id": "remotion", "label": "Remotion", "score": 0.4,
         "reason": "An alternative considered in the historical proposal."},
        {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.6,
         "reason": "The existing work has this explicit runtime lock."},
    ], "hyperframes"))
