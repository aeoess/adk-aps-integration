"""Sign a signed audit receipt for a single Google ADK tool call.

This is the per-call glue. Given an ADK ``ToolContext`` event and a
resolved APS ``DelegationChain``, produce a receipt that carries:

- the delegation chain id and its leaf agent id
- the tool name and arguments (hashed, never verbatim unless the caller
  opts in via ``include_args_verbatim=True``)
- an Ed25519 signature over the canonical receipt bytes

Receipts are written as one JSON file per call into the directory of the
caller's choice. CI can then point ``verify.sh`` at that directory.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from aps_delegation import DelegationChain


class _ToolContextLike(Protocol):
    """Structural type for the bits of ``ToolContext`` this module
    touches. Avoids pinning a hard import of ``google.adk`` at module
    load time so tests can pass in fakes."""

    tool_name: str
    args: dict[str, Any]
    invocation_id: str


@dataclass(frozen=True)
class SignedReceipt:
    receipt_id: str
    payload: dict[str, Any]
    signature_hex: str

    def to_json(self) -> str:
        return json.dumps(
            {"receipt_id": self.receipt_id, "payload": self.payload, "signature": self.signature_hex},
            sort_keys=True,
            separators=(",", ":"),
        )

    def write_to(self, directory: str | Path) -> Path:
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.receipt_id}.json"
        path.write_text(self.to_json())
        return path


def _canonical_args_hash(args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def sign_tool_call(
    tool_context: _ToolContextLike,
    delegation: DelegationChain,
    include_args_verbatim: bool = False,
) -> SignedReceipt:
    """Produce a signed APS receipt for one ADK tool call.

    The signing key is the leaf passport's private key, resolved via the
    APS SDK from the same chain artifact that ``build_delegation_chain``
    wrote to disk.
    """
    from agent_passport_system import Passport, sign  # type: ignore[import-not-found]

    leaf = Passport.from_chain(delegation.signed_chain_path)

    payload: dict[str, Any] = {
        "chain_id": delegation.chain_id,
        "root_agent_id": delegation.root_agent_id,
        "leaf_agent_id": delegation.leaf_agent_id,
        "tool_name": tool_context.tool_name,
        "invocation_id": tool_context.invocation_id,
        "args_hash": _canonical_args_hash(tool_context.args),
        "timestamp": int(time.time()),
        "version": "1",
    }
    if include_args_verbatim:
        payload["args"] = tool_context.args

    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature_hex = sign(canonical_bytes, leaf.private_key).hex()

    receipt_id = hashlib.sha256(canonical_bytes + signature_hex.encode()).hexdigest()[:16]

    return SignedReceipt(
        receipt_id=receipt_id,
        payload=payload,
        signature_hex=signature_hex,
    )
