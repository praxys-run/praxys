"""End User License Agreement (EULA / Terms) version constants.

Single source of truth for the agreement version a new account accepts at
registration. The full document text lives in ``web/src/lib/legal.ts``. Its
canonical bilingual content manifest is hashed by
``miniapp/scripts/sync-legal.cjs``; keep the version and digest below aligned
with the generated web/miniapp contract.
"""
from __future__ import annotations

# Bump on any material change to the Terms/EULA or Privacy summary. Keep in
# sync with web/src/lib/legal.ts::TERMS_VERSION.
TERMS_VERSION = "2026.09.1"
TERMS_CONTENT_DIGEST = (
    "sha256:0fc1448a81e97b5ea0d1fdc9ed831b72d49e0dfae851ff731cfdbe12a8b11805"
)

SUPPORT_EMAIL = "support@praxys.run"
