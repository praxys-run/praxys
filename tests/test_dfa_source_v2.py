from analysis.dfa_source import source_inventory
from api import activity_dfa, dfa_automatic
from fastapi import HTTPException
import pytest


def messages(*devices):
    return [{'frame': 0, 'message':18, 'values':{'sport':1}},
            {'frame': 1, 'message':78, 'values':{'time':[500]}}] + [
            {'frame':i+2, 'message':23, 'values':d} for i,d in enumerate(devices)]


def device(index=1, product=4130, source=1, kind=120):
    return {'device_index':index,'manufacturer':1,'product':product,'source_type':source,'device_type':kind}


@pytest.mark.parametrize('devices,outcome', [
    ([device()], 'eligible_metadata_inferred'),
    ([device(source=3,kind=1)], 'eligible_metadata_inferred'),
    ([device(),device(2,source=3,kind=1)], 'eligible_metadata_inferred'),
    ([device(),{'device_index':0,'manufacturer':1,'product':999,'product_name':'watch optical'}], 'eligible_metadata_inferred'),
    ([device(),device(2,product=3300)], 'source_unresolved'),
    ([device(),{'device_index':2,'manufacturer':999,'source_type':1,'device_type':120}], 'source_unresolved'),
    ([device(),{'device_index':0,'source_type':5,'device_type':10}], 'source_unresolved'),
    ([{k:v for k,v in device().items() if k!='source_type'}], 'source_unresolved'),
    ([{k:v for k,v in device().items() if k!='device_index'}], 'source_unresolved'),
    ([device(),device(product=3300)], 'source_ineligible'),
    ([device(),{'device_index':2,'manufacturer':123,'product_name':'Polar OH1','source_type':3,'device_type':1}], 'source_ineligible'),
    ([device(),device(source=3,kind=1)], 'source_unresolved'),
])
def test_native_matrix(devices,outcome):
    value=source_inventory(messages(*devices), {'snapshot_id':'synthetic'})
    assert value['outcome']==outcome
    assert 'serial' not in str(value)
    if len(devices)==2 and outcome=='eligible_metadata_inferred' and 'source_type' in devices[1]:
        assert len({r['sensor_ref'] for r in value['candidates']})==2


def test_actual_inactive_and_historical_guards():
    for guard in [activity_dfa.require_policy,dfa_automatic.require_policy,activity_dfa.require_historical_v1_policy]:
        with pytest.raises(HTTPException) as exc:
            guard()
        assert exc.value.status_code==503


@pytest.mark.parametrize('phase',['draft','accepted-inactive','projected-active'])
def test_actual_both_origin_projected_policy_guards(monkeypatch,phase):
    from pathlib import Path
    from analysis import science_artifacts as artifacts
    from analysis.evidence_registry import load_science_registry
    from analysis.science_activation import project_active_registry
    from scripts.check_projected_dfa_policy import synthetic_v2_registry
    candidate=Path(__file__).resolve().parents[1]
    registry=load_science_registry(candidate/'data/science')
    expected=artifacts.build_policy_contract(project_active_registry(registry,'sdr-activity-dfa-alpha1-v2'),'sdr-activity-dfa-alpha1-v2').contract_digest
    with synthetic_v2_registry(candidate,phase,expected) as (science,contract):
        monkeypatch.setattr(artifacts,'_SCIENCE_DIR',science)
        for guard in [activity_dfa.require_policy,dfa_automatic.require_policy]:
            if phase=='projected-active':
                assert guard()==contract.contract_digest
            else:
                with pytest.raises(HTTPException): guard()
        with pytest.raises(HTTPException): activity_dfa.require_historical_v1_policy()
        evidence=Path('evidence/activity-dfa-alpha1/evidence-activity-dfa-alpha1-v1.yaml')
        stop=Path('stops/sdr-activity-dfa-alpha1-v1.yaml')
        assert (science/evidence).read_bytes()==(candidate/'data/science'/evidence).read_bytes()
        assert (science/stop).read_bytes()==(candidate/'data/science'/stop).read_bytes()
