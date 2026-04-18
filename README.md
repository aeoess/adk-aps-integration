# adk-aps-integration

**Authors:** Tymofii Pidlisnyi ([@aeoess](https://github.com/aeoess)) and Thomas Farley ([@tomjwxf](https://github.com/tomjwxf))

APS integration for Google's [Agent Development Kit](https://github.com/google/adk-python).

The APS identity and delegation layer bridges to ADK's tool-call system.
Every ADK tool call is wrapped in an APS delegation check at evaluation
time and emits a signed audit receipt that any external verifier can
check offline, without talking back to the runtime that produced it.

Committed on [google/adk-python#5164](https://github.com/google/adk-python/issues/5164).

## Three primitives

Everything in this repo reduces to three files:

| File | Role |
|------|------|
| [`aps_delegation.py`](./aps_delegation.py) | Set up an APS delegation chain once per agent. |
| [`receipt_signing.py`](./receipt_signing.py) | Wrap an ADK `ToolContext` event, produce a signed receipt. |
| [`verify.sh`](./verify.sh) | Standalone shell script a CI job can run as a gate. |

## Quick start

```python
from aps_delegation import build_delegation_chain
from receipt_signing import sign_tool_call

# 1. Once per agent: set up APS delegation chain.
chain = build_delegation_chain(
    principal_passport_path="passport.json",
    agent_scope=["tool:search", "tool:http_get"],
    spend_limit_usd=5.0,
)

# 2. On every tool call: sign a receipt.
def on_tool_call(tool_context):
    receipt = sign_tool_call(tool_context, delegation=chain)
    receipt.write_to("receipts/")
```

```bash
# 3. In CI: gate on receipt validity.
./verify.sh receipts/
# exit 0 = pass, 1 = signature fail, 2 = chain gap
```

## Example

See [`examples/basic-tool-call/`](./examples/basic-tool-call/) for an end-to-end
run: delegation setup, a mock ADK tool call, receipt emission, and verification
against `@veritasacta/verify`.

## CI matrix

CI runs the example against every combination of:

| APS SDK | `@veritasacta/verify` |
|---------|-----------------------|
| `agent-passport-system@latest` | `@veritasacta/verify@0.3.0` |
| `agent-passport-system@next` | `@veritasacta/verify@latest` |
| `agent-passport-system==2.0.0b0` (PyPI) | |

Three APS versions × two verifier versions = six jobs. A new release of
either side that breaks the matrix is caught before it ships.

See [`.github/workflows/ci.yaml`](./.github/workflows/ci.yaml).

## Verifier compatibility

Receipts emitted by this integration verify offline against
[`@veritasacta/verify`](https://www.npmjs.com/package/@veritasacta/verify)
versions 0.3.0 and later, per the
[`draft-farley-acta-signed-receipts`](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/)
wire format.

## Status

Skeleton. CI matrix is wired; example runs end-to-end as a mock. Not yet
production-polished. See the `integration-skeleton` branch for the working
tree that's open for collaboration.

## License

Apache-2.0. See [LICENSE](./LICENSE).
