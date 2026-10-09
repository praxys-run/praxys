"""Untrusted candidate observation child. Stdlib only until candidate imports."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def observe_v2(candidate, science):
    # Imported only after the fresh interpreter has established candidate root.
    import inspect
    from api import activity_dfa as manual, dfa_automatic as automatic
    from analysis import activity_dfa as method, dfa_source as source
    from analysis import science_artifacts as artifacts, evidence_registry, science_implementation_stop as stops
    from fastapi import HTTPException
    phase = sys.argv[4]
    if phase not in {'draft', 'accepted-inactive', 'projected-active'}:
        raise ValueError('Unknown V2 phase')
    designated = 'sdr-activity-dfa-alpha1-v2'
    if method.SDR_ID != designated or source.AUTO_SDR_ID != designated:
        raise RuntimeError('Future V2 guard identities are missing or differ')
    artifacts._SCIENCE_DIR = science
    registry = evidence_registry.load_science_registry(science)
    contract = artifacts.build_policy_contract(registry, designated)
    modules = (manual, method, artifacts, evidence_registry, stops, automatic, source)
    module_paths = {m.__name__: str(Path(m.__file__).resolve()) for m in modules}
    observations, callables = {}, {}
    for branch, module, name in [('historical_v1', manual, 'require_historical_v1_policy'),
                                  ('manual', manual, 'require_policy'), ('automatic', automatic, 'require_policy')]:
        function = getattr(module, name, None)
        if (not inspect.isfunction(function) or function.__module__ != module.__name__
                or function.__name__ != name or Path(function.__code__.co_filename).resolve() != Path(module.__file__).resolve()):
            raise RuntimeError('Future actual guard callable is missing or provenance differs')
        callables[branch] = dict(module=function.__module__, name=function.__name__,
                                 source=str(Path(function.__code__.co_filename).resolve()))
        try:
            returned = function()
        except HTTPException as error:
            observations[branch] = dict(http_status=error.status_code, detail=error.detail)
        else:
            fingerprint_module = automatic if branch == 'automatic' else method
            observations[branch] = dict(returned_contract=returned, method_version=fingerprint_module.METHOD_VERSION,
                                        parameter_digest=fingerprint_module.POLICY_PARAMETER_DIGEST)
    projected_digest = contract.contract_digest if phase == 'projected-active' else projected_contract_digest(registry, designated)
    dependencies = verify_dependencies(candidate)
    matching = [s for s in stops.load_implementation_stops(science) if s.subject_id == 'sdr-activity-dfa-alpha1-v1']
    if len(matching) != 1:
        raise RuntimeError('Real historical V1 STOP must be retained')
    print(json.dumps(dict(schema_version=2, purpose='dfa-v2-activation', subject_id=designated,
        phase=phase, contract_digest=projected_digest,
        baseline_stop_digest=matching[0].stop_digest, module_paths=module_paths, candidate_dependencies=dependencies,
        callables=callables, observation=observations), sort_keys=True))


def projected_contract_digest(registry, subject):
    from analysis.science_activation import project_active_registry
    from analysis.science_artifacts import build_policy_contract
    return build_policy_contract(project_active_registry(registry, subject), subject).contract_digest


def verify_dependencies(candidate):
    dependencies = {}
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in ('analysis', 'api', 'db', 'sync'):
            path = getattr(module, '__file__', None)
            if path is None or not Path(path).resolve().is_relative_to(candidate):
                raise RuntimeError('Candidate dependency resolved outside frozen candidate')
            dependencies[name] = str(Path(path).resolve())
    return dependencies


def main():
    candidate, science = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    purpose = sys.argv[3]
    namespaces = ('analysis', 'api', 'db', 'sync')
    if any(name.split('.')[0] in namespaces for name in sys.modules):
        raise RuntimeError('Candidate modules were cached before the fresh observer')
    sys.path.insert(0, str(candidate))
    if purpose == 'dfa-v2-activation':
        observe_v2(candidate, science)
        return
    from api import activity_dfa
    from analysis import activity_dfa as method
    from analysis import science_artifacts as artifacts
    from analysis import evidence_registry
    from analysis import science_implementation_stop as stops
    from fastapi import HTTPException

    observed_subject = method.SDR_ID
    if purpose == 'activation':
        # Change only the disposable registry path, never the guard implementation.
        artifacts._SCIENCE_DIR = science
        returned = activity_dfa.require_policy()
        observation = dict(returned_contract=returned, method_version=method.METHOD_VERSION,
                           parameter_digest=method.POLICY_PARAMETER_DIGEST)
        contract_digest = returned
        stop_fields = {}
    elif purpose == 'stopped-maintenance':
        if artifacts._SCIENCE_DIR.resolve() != science or science != candidate / 'data/science':
            raise RuntimeError('Stopped probe must use the unchanged candidate registry')
        observed_subject = 'sdr-activity-dfa-alpha1-v1'
        function = activity_dfa.require_policy
        if method.SDR_ID == 'sdr-activity-dfa-alpha1-v2':
            import inspect
            function = getattr(activity_dfa, 'require_historical_v1_policy', None)
            if (not inspect.isfunction(function) or function.__module__ != activity_dfa.__name__
                    or function.__name__ != 'require_historical_v1_policy'
                    or Path(function.__code__.co_filename).resolve() != Path(activity_dfa.__file__).resolve()):
                raise RuntimeError('Historical V1 actual callable missing or provenance differs')
        elif method.SDR_ID != observed_subject:
            raise RuntimeError('Unknown actual historical guard identity')
        try:
            returned = function()
        except HTTPException as error:
            observation = dict(http_status=error.status_code, detail=error.detail)
        else:
            observation = dict(returned_contract=returned)
        registry = evidence_registry.load_science_registry(science)
        contract_digest = artifacts.build_policy_contract(registry, observed_subject).contract_digest
        matching = [stop for stop in stops.load_implementation_stops(science) if stop.subject_id == observed_subject]
        if len(matching) != 1:
            raise RuntimeError('Observed candidate must retain exactly one subject stop')
        stop_fields = {'stop_digest': matching[0].stop_digest}
    else:
        raise ValueError('Unknown observation purpose')

    # Actual dependency provenance is observed after execution. It is untrusted
    # child data, checked by the controller; source review remains indispensable.
    module_paths = {module.__name__: str(Path(module.__file__).resolve())
                    for module in (activity_dfa, method, artifacts, evidence_registry, stops)}
    verify_dependencies(candidate)
    print(json.dumps(dict(schema_version=1, purpose=purpose, subject_id=observed_subject,
                          contract_digest=contract_digest, observation=observation,
                          module_paths=module_paths, **stop_fields), sort_keys=True))


if __name__ == '__main__':
    main()
