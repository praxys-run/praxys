"""Deterministic whole-file scheduling hints; these weights never select coverage."""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median

DEFAULT_WEIGHTS = Path(__file__).resolve().parents[1] / 'config/ci-test-weights.json'
DATABASE_GROUP = {'tests/test_pg_migration.py', 'tests/test_activity_dfa.py'}


def load_weights(path: Path = DEFAULT_WEIGHTS) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get('schema_version') != 1 or not isinstance(value.get('files'), dict):
        raise ValueError('Invalid shard weights schema')
    if not value['files'] or any(not isinstance(name, str) or type(weight) not in (int, float)
                                 or not math.isfinite(weight) or weight <= 0
                                 for name, weight in value['files'].items()):
        raise ValueError('Shard weights must be positive finite file durations')
    groups = value.get('groups')
    if not isinstance(groups, list) or not all(isinstance(group, list) and group
                                               and all(isinstance(name, str) for name in group) for group in groups):
        raise ValueError('Invalid shard affinity groups')
    members = [name for group in groups for name in group]
    if len(members) != len(set(members)) or not any(DATABASE_GROUP <= set(group) for group in groups):
        raise ValueError('Database affinity must be preserved without overlapping groups')
    return value, sha256(raw).hexdigest()


def plan_files(nodeids: list[str], weights: dict) -> list[list[str]]:
    """Two bins, longest grouped file weight first; stable ties and unknown fallback."""
    files = {node.split('::', 1)[0] for node in nodeids}
    fallback = median(weights['files'].values())
    units = []
    for group in weights['groups']:
        members = sorted(files.intersection(group))
        if members:
            units.append(members)
            files.difference_update(members)
    units.extend([name] for name in sorted(files))
    def cost(unit):
        return sum(weights['files'].get(name, fallback) for name in unit)
    bins, totals = [[], []], [0.0, 0.0]
    for unit in sorted(units, key=lambda unit: (-cost(unit), unit)):
        index = min(range(2), key=lambda candidate: (totals[candidate], candidate))
        bins[index].extend(unit)
        totals[index] += cost(unit)
    return [sorted(bucket) for bucket in bins]


def selected_nodes(nodeids: list[str], shard_index: int, weights: dict) -> list[str]:
    selected = set(plan_files(nodeids, weights)[shard_index])
    return [node for node in nodeids if node.split('::', 1)[0] in selected]
