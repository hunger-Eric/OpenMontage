"""Protect the one complete-plan production gate and real checkpoint behavior."""
import json
from pathlib import Path

import pytest
from lib.pipeline_loader import load_pipeline_readonly, list_pipelines
from lib.checkpoint import init_project, write_checkpoint, CheckpointValidationError, CANONICAL_STAGE_ARTIFACTS
from tests.contracts.test_phase0_contracts import sample_artifact

PRODUCTION = [name for name in list_pipelines() if name != 'framework-smoke']


@pytest.mark.parametrize('name', PRODUCTION)
def test_production_has_one_plan_gate_and_no_sample_substage(name):
    manifest = load_pipeline_readonly(name)
    stages = manifest['stages']
    gates = {s['name'] for s in stages if s.get('human_approval_default')}
    publication_gate = {s['name'] for s in stages if s['name'] == 'publish' and s.get('human_approval_default')}
    assert gates == {'scene_plan'} | publication_gate
    scene = next(s for s in stages if s['name'] == 'scene_plan')
    assert {'image_selector', 'feishu_video_plan'} <= set(scene['tools_available'])
    assert not any(sub['name'] == 'sample' for stage in stages for sub in stage.get('sub_stages', []))


def test_actual_checkpoint_waits_for_plan_then_assets_complete_without_second_approval(tmp_path):
    project = init_project('confirmation-test', title='Contract fixture', pipeline_type='cinematic', pipeline_dir=tmp_path, open_board=False)
    manifest = load_pipeline_readonly('cinematic')
    for stage in manifest['stages']:
        name = stage['name']
        if name == 'scene_plan':
            break
        artifact = CANONICAL_STAGE_ARTIFACTS[name]
        write_checkpoint(tmp_path, project.name, name, 'completed', {artifact: sample_artifact(artifact)}, pipeline_type='cinematic')
    scenes = {'scene_plan': sample_artifact('scene_plan')}
    metadata = {'plan_board': {'url': 'https://example.test/plan', 'plan_sha256': 'a'*64, 'receipt_path': 'artifacts/feishu-video-plan-delivery.json', 'execution_mode': 'automatic'}}
    pending = write_checkpoint(tmp_path, project.name, 'scene_plan', 'awaiting_human', scenes, metadata=metadata)
    assert json.loads(pending.read_text())['metadata']['plan_board'] == metadata['plan_board']
    with pytest.raises(CheckpointValidationError, match='GATE VIOLATION'):
        write_checkpoint(tmp_path, project.name, 'scene_plan', 'completed', scenes)
    with pytest.raises(CheckpointValidationError, match='PREREQUISITE VIOLATION'):
        write_checkpoint(tmp_path, project.name, 'assets', 'completed', {'asset_manifest': sample_artifact('asset_manifest')})
    write_checkpoint(tmp_path, project.name, 'scene_plan', 'completed', scenes, human_approved=True, metadata=metadata)
    assets = write_checkpoint(tmp_path, project.name, 'assets', 'completed', {'asset_manifest': sample_artifact('asset_manifest')})
    assert json.loads(assets.read_text())['human_approval_required'] is False
