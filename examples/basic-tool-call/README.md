# basic-tool-call

End-to-end example: create a delegation, run a mock ADK tool call, emit a
signed receipt, verify it.

## What it does

1. `run.py` builds a delegation chain from a test principal passport
   (`fixtures/principal_passport.json`) down to a fresh session agent.
2. It calls a fake `search` tool via a `FakeToolContext` object shaped
   like ADK's `ToolContext`.
3. `receipt_signing.sign_tool_call` signs each tool call as a v2
   verify-artifact envelope, and `write_audit_bundle` rolls them into
   `receipts/bundle.json` along with the leaf agent's public JWK.
4. The included `../../verify.sh` is then run against `receipts/` and
   must exit 0.

## Running locally

```bash
pip install agent-passport-system
npm install @veritasacta/verify

python run.py
../../verify.sh receipts/
```

The example uses a fake tool context so the repo has no hard dependency
on `google-adk` being installed. Swap `FakeToolContext` for a real
`google.adk.tools.ToolContext` in production.

## Exit codes from verify.sh

- `0` — bundle signature(s) valid (every receipt verifies)
- `1` — at least one receipt failed signature check
- `3` — usage error or malformed bundle
