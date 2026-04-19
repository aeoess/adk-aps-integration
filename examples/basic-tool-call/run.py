"""End-to-end walk-through: delegation → tool call → receipt → bundle.

Run with: ``python run.py``. Produces ``receipts/bundle.json`` ready
for ``../../verify.sh receipts/`` to gate on.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aps_delegation import build_delegation_chain  # noqa: E402
from receipt_signing import sign_tool_call, write_audit_bundle  # noqa: E402


@dataclass
class FakeToolContext:
    """Shaped like ADK's ToolContext for the minimal surface we need."""

    tool_name: str
    args: dict[str, Any]
    invocation_id: str


def main() -> None:
    here = Path(__file__).parent

    chain = build_delegation_chain(
        principal_passport_path=here / "fixtures" / "principal_passport.json",
        agent_scope=["tool:search"],
        spend_limit_usd=1.0,
        output_dir=here / "delegations",
    )

    calls = [
        FakeToolContext(
            tool_name="search",
            args={"query": "ADK receipt signing example", "limit": 3},
            invocation_id="inv-0001",
        ),
        FakeToolContext(
            tool_name="search",
            args={"query": "monotonic narrowing in delegation chains", "limit": 5},
            invocation_id="inv-0002",
        ),
    ]

    receipts = [sign_tool_call(c, delegation=chain) for c in calls]
    bundle_path = write_audit_bundle(
        receipts=receipts,
        delegation=chain,
        output_path=here / "receipts" / "bundle.json",
        description=(
            f"ADK basic-tool-call example: {len(receipts)} call(s) under "
            f"delegation {chain.delegation_id}"
        ),
    )
    print(f"audit bundle: {bundle_path} ({len(receipts)} receipts)")


if __name__ == "__main__":
    main()
