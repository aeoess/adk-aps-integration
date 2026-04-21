# Full composition: APS delegation + protect-mcp-adk receipts

This example demonstrates the three-component composition agreed on adk-python#5164:

1. **APS delegation** (pre-execution authorization)
2. **protect-mcp-adk ReceiptPlugin** (post-decision Ed25519 receipt signing via the official plugin on PyPI)
3. **ADK executes** the tool call if permitted

Each layer produces its own signed artifact with its own key. A verifier consuming the output can check any layer independently:

| Layer | Artifact | Signer | What it proves |
|---|---|---|---|
| APS delegation chain | `delegations/*.json` | Principal's Ed25519 key | The agent was authorized with scope `tool:search` under spend limit $1.00 |
| protect-mcp-adk receipt | `receipts/bundle.json` entries | Agent's Ed25519 key (via `ReceiptSigner`) | The tool call happened with input hash X, output hash Y, under policy P |

Both verify against the same reference CLI (`npx @veritasacta/verify`) at exit 0 when the chain is intact.

## Why this shape

The three components are not coupled at runtime:

- APS `GovernanceHook` checks delegation scope BEFORE the tool runs. If the scope check fails, execution is blocked and no receipt is emitted.
- `protect-mcp-adk.ReceiptPlugin` signs the decision AFTER the policy gate evaluates. The receipt is the proof artifact.
- ADK itself executes the tool call if both layers permit it.

Users can install just APS, just protect-mcp-adk, or both. The receipts compose at verification time, not at runtime. No federation, no coordination service, no shared key material.

## Install

```bash
pip install protect-mcp-adk agent-passport-system
```

## Run

```bash
python run.py
```

Produces:
- `delegations/<chain-id>.json` — the APS delegation chain this agent operates under
- `receipts/bundle.json` — the audit bundle containing protect-mcp-adk signed receipts

## Verify

```bash
../../verify.sh receipts/
```

Exits 0 when all receipts verify and the chain is intact.

## Deterministic seed

Receipts in this example use a fixed Ed25519 seed from `fixtures/agent_seed.json` so the output is byte-reproducible. Regenerate with a random seed by removing the fixture file; `run.py` will use `ReceiptSigner.generate()` in that case.

## Cross-verification

Receipts produced by this example are byte-compatible with receipts produced by:

- `protect-mcp` (TypeScript/Node) at https://github.com/ScopeBlind/scopeblind-gateway
- `sb-runtime` (Rust) at https://github.com/ScopeBlind/sb-runtime
- `APS governance hook` at https://github.com/aeoess/agent-passport-system

All four implementations pass the shared fixtures at `github.com/ScopeBlind/agent-governance-testvectors` at `verify` exit 0. This example extends the set to include ADK-hosted runs of the same pattern.
