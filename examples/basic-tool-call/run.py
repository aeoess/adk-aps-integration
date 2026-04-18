"""End-to-end walk-through: delegation → tool call → receipt → verify."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aps_delegation import build_delegation_chain  # noqa: E402
from receipt_signing import sign_tool_call  # noqa: E402


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

    tool_context = FakeToolContext(
        tool_name="search",
        args={"query": "ADK receipt signing example", "limit": 3},
        invocation_id="inv-0001",
    )

    receipt = sign_tool_call(tool_context, delegation=chain)
    path = receipt.write_to(here / "receipts")
    print(f"signed receipt: {path}")


if __name__ == "__main__":
    main()
