# Contributing

Thanks for your interest.

This repo is the glue layer between APS and Google ADK. PRs here should
stay focused on:

- `aps_delegation.py`, `receipt_signing.py`, `verify.sh` — the three
  integration primitives
- `examples/` — minimal runnable examples
- `.github/workflows/ci.yaml` — the compatibility matrix

## Where changes belong

| If your change is about... | Open a PR against... |
|----------------------------|----------------------|
| Core APS protocol, SDK functions, delegation semantics | [`aeoess/agent-passport-system`](https://github.com/aeoess/agent-passport-system) |
| The receipt wire format | [`draft-farley-acta-signed-receipts`](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/) |
| The verifier | [`@veritasacta/verify`](https://www.npmjs.com/package/@veritasacta/verify) |
| ADK tool-call glue, example runs, CI matrix | This repo |

See APS's own [CONTRIBUTING](https://github.com/aeoess/agent-passport-system/blob/main/CONTRIBUTING.md)
for the APS-side contribution process (DCO, test requirements, review flow).

## Local checks before opening a PR

```bash
python examples/basic-tool-call/run.py
./verify.sh examples/basic-tool-call/receipts/
```

Both must exit 0 on at least one row of the CI matrix (any APS SDK
version paired with any verifier version).

## Co-maintainers

- Tymofii Pidlisnyi ([@aeoess](https://github.com/aeoess)) — APS side
- Thomas Farley ([@tomjwxf](https://github.com/tomjwxf)) — ADK and ACTA side
