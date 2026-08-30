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
TERMS_VERSION = "2026.08.4"
TERMS_CONTENT_DIGEST = (
    "sha256:ce863ba3531157c50775509c8a8061654d24868cafe0b7f22ede02ca60c65aa1"
)

SUPPORT_EMAIL = "support@praxys.run"
