"""End User License Agreement (EULA / Terms) version constants.

Single source of truth for the agreement version a new account accepts at
registration. Stored on User.terms_version so we can prove which version each
user agreed to. The full document text lives in the web client
(web/src/pages/Terms.tsx, web/src/pages/Privacy.tsx); bump TERMS_VERSION here
and the EFFECTIVE_DATE there together whenever the agreement materially changes.
"""
from __future__ import annotations

# Bump on any material change to the Terms/EULA or Privacy summary. Keep in
# sync with web/src/lib/legal.ts::TERMS_VERSION.
TERMS_VERSION = "2026.06.2"

SUPPORT_EMAIL = "support@praxys.run"
