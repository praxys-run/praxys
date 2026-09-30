"""Explicitly loaded pytest evidence collector; never inherited by child pytest."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption('--ci-report', help='Write serial CI collection and phase evidence')


def pytest_configure(config):
    destination = config.getoption('--ci-report')
    if destination:
        config.pluginmanager.register(EvidenceCollector(Path(destination)), 'ci-evidence')


def _reason(report):
    if getattr(report, 'wasxfail', None):
        return str(report.wasxfail)
    if report.skipped:
        return str(report.longrepr[-1] if isinstance(report.longrepr, tuple) else report.longrepr)
    if report.failed and str(report.longrepr).startswith('[XPASS(strict)]'):
        return str(report.longrepr)
    return None


class EvidenceCollector:
    def __init__(self, destination: Path):
        self.destination = destination
        self.data = dict(schema_version=1, mode='serial', collection_complete=False,
                         session_finished=False, full_collected=[], selected=[],
                         deselected=[], collection_reports=[], phases=[], exit_code=None)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_collection_modifyitems(self, items):
        self.data['full_collected'] = [item.nodeid for item in items]
        result = yield
        self.data['selected'] = [item.nodeid for item in items]
        return result

    def pytest_collection_finish(self, session):
        self.data['collection_complete'] = not session.testsfailed

    def pytest_deselected(self, items):
        self.data['deselected'].extend(item.nodeid for item in items)

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            self.data['collection_reports'].append(dict(
                nodeid=report.nodeid, outcome=report.outcome, reason=_reason(report)))

    def pytest_runtest_logreport(self, report):
        self.data['phases'].append(dict(
            nodeid=report.nodeid, phase=report.when, outcome=report.outcome,
            duration_seconds=report.duration, reason=_reason(report),
            wasxfail=getattr(report, 'wasxfail', None),
            strict_xpass=report.failed and str(report.longrepr).startswith('[XPASS(strict)]')))

    def pytest_sessionfinish(self, session, exitstatus):
        self.data.update(session_finished=True, exit_code=int(exitstatus))
        temporary = self.destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, indent=2) + '\n', encoding='utf-8')
        temporary.replace(self.destination)
