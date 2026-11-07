# Local and Cloud Copilot execution

Local and Cloud use `.github/agents/praxys-orchestrator.agent.md` to execute in
one session. An existing session follows it directly. The session loads domain
skills, runs appropriate checks, and requests one fresh read-only Quality review
for material risk. It does not invoke routing agents or nested loops.

The common policy is [single-session execution](agentic-operating-model.md).
`config/copilot-execution-parity.json` defines portable tool capabilities and
explicit environment limitations. `scripts/check_copilot_environment_parity.py`
checks static configuration; its existing `--live` mode checks Cloud settings.
The workflow selecting `praxys-orchestrator` for agent-ready issues is unchanged.

Public-source access uses the isolated browser. Product-context tools use the
read-only synthetic profile. Local production tools are outside the portable
baseline, keep their existing consent boundaries, and cannot substitute for
missing Cloud tools. Required unavailable browser or WeChat rendering evidence
keeps the dependent PR in draft. It does not prevent unrelated local work.

`AGENTS.md` defines the working loop and review threshold directly. No task
classifier or digest output is required. Both runtimes reuse scoped authority
and preserve science, CI and branch protection. Native runtimes own lifecycle.

Static configuration parity does not imply equal prose, quality, elapsed time or
successful native transport. Changes to Cloud custom agents take effect through
normal default-branch activation; a local test is not evidence of that activation.
