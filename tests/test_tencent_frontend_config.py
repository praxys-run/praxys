"""Regression tests for the Tencent-hosted praxys.cn frontend."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_tencent_nginx_serves_the_filed_cn_hosts() -> None:
    config = (ROOT / "deploy/tencent/nginx-praxys.conf").read_text(encoding="utf-8")

    assert "server_name praxys.cn www.praxys.cn;" in config
    assert "server_name www.praxys.run" not in config
    assert "server_name origin-cn.praxys.run" not in config
    assert "return 444;" in config
    assert "return 308 https://$host$request_uri;" in config
    assert "listen 443 ssl default_server;" in config
    assert "ssl_certificate /etc/praxys/tls/fullchain.pem;" in config
    assert "ssl_certificate_key /etc/praxys/tls/privkey.pem;" in config


def test_tencent_artifact_is_stamped_without_mutating_the_azure_package() -> None:
    workflow = (
        ROOT / ".github/workflows/deploy-frontend-appservice.yml"
    ).read_text(encoding="utf-8")

    azure_stage = workflow.index("cp -r web/dist deploy-pkg/web/dist")
    china_copy = workflow.index("cp -a web/dist china-dist")
    china_stamp = workflow.index(
        "node web/scripts/stamp-china-compliance.mjs china-dist"
    )
    china_archive = workflow.index(
        "tar -C china-dist -czf tencent-package/praxys-web.tgz ."
    )

    assert azure_stage < china_copy < china_stamp < china_archive
    assert (
        "cp deploy/tencent/nginx-praxys.conf "
        "tencent-package/nginx-praxys.conf"
    ) in workflow
    assert 'cmp --silent "${expected_nginx}" "${installed_nginx}"' in workflow
    assert 'test "${redirect}" = "308 https://${host}/"' in workflow
    assert '--resolve "${host}:443:127.0.0.1"' in workflow
    assert "for host in praxys.cn www.praxys.cn" in workflow
    assert "沪ICP备2025109616号-2" in workflow
    assert '--resolve "unknown.invalid:443:127.0.0.1"' in workflow
    assert 'test "${unknown_status}" = "000"' in workflow


def test_runbook_keeps_cn_direct_and_run_on_non_mainland_edgeone() -> None:
    runbook = (ROOT / "docs/ops/tencent-frontend.md").read_text(encoding="utf-8")
    normalized = " ".join(runbook.split())

    assert "`praxys.cn` resolves directly to the Lighthouse public IP" in normalized
    assert "`praxys.run` remains on its existing EdgeOne site" in normalized
    assert "global availability zone excluding the Chinese mainland" in normalized
    assert "HTTP `302`" in normalized
    assert "Do not add `praxys.cn` as a second site" in normalized
