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
TERMS_VERSION = "2026.08.5"
TERMS_CONTENT_DIGEST = (
    "sha256:57cca8f824f6e803a3df9b1de45d76cfc21fb750483e61281e7c4ff495ae218e"
)

SUPPORT_EMAIL = "support@praxys.run"
