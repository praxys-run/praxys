"""Untrusted candidate observation child. Stdlib only until candidate imports."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def main():
    candidate, science = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    purpose = sys.argv[3]
    namespaces = ('analysis', 'api', 'db', 'sync')
    if any(name.split('.')[0] in namespaces for name in sys.modules):
        raise RuntimeError('Candidate modules were cached before the fresh observer')
    sys.path.insert(0, str(candidate))
    from api import activity_dfa
    from analysis import activity_dfa as method
    from analysis import science_artifacts as artifacts
    from analysis import evidence_registry
    from analysis import science_implementation_stop as stops
    from fastapi import HTTPException

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
        try:
            returned = activity_dfa.require_policy()
        except HTTPException as error:
            observation = dict(http_status=error.status_code, detail=error.detail)
        else:
            observation = dict(returned_contract=returned)
        registry = evidence_registry.load_science_registry(science)
        contract_digest = artifacts.build_policy_contract(registry, method.SDR_ID).contract_digest
        matching = [stop for stop in stops.load_implementation_stops(science) if stop.subject_id == method.SDR_ID]
        if len(matching) != 1:
            raise RuntimeError('Observed candidate must retain exactly one subject stop')
        stop_fields = {'stop_digest': matching[0].stop_digest}
    else:
        raise ValueError('Unknown observation purpose')

    # Actual dependency provenance is observed after execution. It is untrusted
    # child data, checked by the controller; source review remains indispensable.
    module_paths = {module.__name__: str(Path(module.__file__).resolve())
                    for module in (activity_dfa, method, artifacts, evidence_registry, stops)}
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in namespaces:
            path = getattr(module, '__file__', None)
            if path is None or not Path(path).resolve().is_relative_to(candidate):
                raise RuntimeError('Candidate dependency resolved outside frozen candidate')
    print(json.dumps(dict(schema_version=1, purpose=purpose, subject_id=method.SDR_ID,
                          contract_digest=contract_digest, observation=observation,
                          module_paths=module_paths, **stop_fields), sort_keys=True))


if __name__ == '__main__':
    main()
