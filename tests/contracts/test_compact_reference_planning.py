"""Compact plans retain the canonical contracts without padding alternatives."""
from copy import deepcopy

import pytest
from jsonschema.exceptions import ValidationError

from schemas.artifacts import validate_artifact
from tests.contracts.test_phase0_contracts import sample_artifact


def test_one_selected_concept_is_a_valid_proposal():
    proposal = deepcopy(sample_artifact("proposal_packet"))
    proposal["concept_options"] = proposal["concept_options"][:1]
    validate_artifact("proposal_packet", proposal)


def test_selected_concept_must_still_exist_after_compacting_options():
    proposal = deepcopy(sample_artifact("proposal_packet"))
    proposal["concept_options"] = proposal["concept_options"][:1]
    proposal["selected_concept"]["concept_id"] = "removed-concept"
    with pytest.raises(ValidationError, match="selected_concept"):
        validate_artifact("proposal_packet", proposal)


@pytest.mark.parametrize("field", ["data_points", "sources"])
def test_confirmed_direction_keeps_original_research_requirements(field):
    brief = deepcopy(sample_artifact("research_brief"))
    brief[field] = brief[field][:1]
    with pytest.raises(ValidationError):
        validate_artifact("research_brief", brief)


@pytest.mark.parametrize("name,field", [("proposal_packet", "concept_options"), ("research_brief", "sources")])
def test_compact_planning_still_rejects_empty_evidence(name, field):
    artifact = deepcopy(sample_artifact(name))
    artifact[field] = []
    with pytest.raises(ValidationError):
        validate_artifact(name, artifact)


def test_full_existing_proposals_and_research_remain_valid():
    for name in ("proposal_packet", "research_brief"):
        validate_artifact(name, sample_artifact(name))
