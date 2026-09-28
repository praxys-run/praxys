"""Bounded, payload-free DFA activation observation after normal restoration."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import sys
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def expected_policy(contract_path: Path):
    from analysis.science_artifacts import load_policy_contract
    from analysis.science_implementation_stop import load_implementation_stops
    raw = json.loads(contract_path.read_text())
    science = contract_path.resolve().parents[2]
    contract = load_policy_contract(raw["decision_id"], science_dir=science)
    stopped = any(stop.subject_id == contract.decision_id for stop in load_implementation_stops(science))
    active = contract.runtime_state.value == "active" and contract.decision_status.value == "accepted" and not stopped
    return active, contract.contract_digest if active else None


def validate_observation(ready, version, *, expected_sha, expected_active, expected_digest):
    policy = ready.get('dfa_policy')
    if (not isinstance(policy, dict) or set(policy) != {'policy_active', 'contract_digest'}
            or type(policy['policy_active']) is not bool
            or policy != {'policy_active': expected_active, 'contract_digest': expected_digest}
            or ready.get('status') != 'ready' or version.get('source_sha') != expected_sha):
        raise ValueError('DFA policy observation does not match deployed source and exact contract')
    return {'source_sha': expected_sha, **policy, 'observed_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--base-url', default='https://api.praxys.run')
    parser.add_argument('--timeout-seconds', type=int, default=1200)
    args = parser.parse_args()
    active, digest = expected_policy(args.contract)
    deadline = time.monotonic() + min(max(args.timeout_seconds, 1), 1200)
    while True:
        try:
            def read(path):
                request = Request(args.base_url + path, headers={'Cache-Control': 'no-cache'})
                with urlopen(request, timeout=8) as response:
                    if path.endswith('/ready') and response.headers.get('Cache-Control') != 'no-store':
                        raise ValueError('DFA readiness must be no-store')
                    raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError('Observation response exceeds fixed bound')
                return json.loads(raw)
            evidence = validate_observation(read('/api/health/ready'), read('/api/version'),
                                            expected_sha=args.source_sha, expected_active=active,
                                            expected_digest=digest)
            print(json.dumps(evidence, sort_keys=True))
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise SystemExit('DFA policy observation failed within the bounded window') from None
            time.sleep(5)


if __name__ == '__main__':
    main()
