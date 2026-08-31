# ADR-2026-08-30 Codex local Microsoft MCP extensions

- **artifact_type:** `architecture-decision-record`
- **owner_role:** Architecture
- **status:** Human-accepted boundary for bounded implementation and
  verification; independent Architecture agent invocation unavailable
- **decision subject digest:**
  `sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d`

This draft was prepared because the Architecture role invocation received an
empty payload and failed closed. The human authority explicitly reviewed and
accepted this Architecture boundary with the bound subject digest. It does not
claim an independent Architecture-agent review or approve its own
implementation.

## Question and options

How should Codex access current Microsoft documentation and limited live Azure
topology without making production tooling part of every role or of the
portable Local/Cloud baseline?

Options are: no new integration; Microsoft Learn only; broad Azure MCP; or two
disabled project registrations with exact role projections. The last option is
recommended for review because it separates public knowledge from authenticated
production metadata while preserving a small root tool surface.

## Proposed boundary

- Microsoft Learn is remote HTTPS, credential-free, and limited to its three
  public documentation tools. It may be projected into Architecture,
  Engineering, Operations, and Trust.
- Azure MCP is local stdio, pinned to `@azure/mcp@2.0.5`, uses `--mode all`
  only so Codex can enforce two individually named tools, and also uses
  `--read-only`. It is projected only into Operations.
- Root registrations remain disabled. No router gains either capability.
- Azure MCP is a Codex-local extension, not a portable capability; Copilot
  parity remains measured against the original common set.
- Repository workflows and Operations runbooks remain the execution boundary.

## Failure and rollback

Missing documentation access degrades only the documentation lookup. Missing
Azure package/authentication or tool drift blocks Azure-assisted diagnosis. No
role may replace failure with broader tools or credentials. Rollback removes
the extension contract, registrations, and role projections without changing
the v1 adapter or production state.
