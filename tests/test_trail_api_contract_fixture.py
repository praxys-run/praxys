"""Cross-layer regression for the actual Trail service/client fixture."""
from __future__ import annotations

import json

from tests.trail_api_contract_fixture import (
    FIXTURE_PATH,
    build_trail_readiness_contract_fixture,
)


def test_trail_readiness_fixture_matches_actual_service_serialization():
    tracked = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert tracked == build_trail_readiness_contract_fixture()
