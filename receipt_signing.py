"""Sign a signed audit receipt for a single Google ADK tool call.

This is the per-call glue. Given an ADK ``ToolContext`` event and a
resolved APS ``DelegationChain``, produce a v2 receipt envelope that
``@veritasacta/verify`` can check offline. Each receipt carries:

- the delegation chain id and its leaf agent id
- the APS delegation id (so verifiers can pull the chain and walk it)
- the tool name and arguments (hashed, never verbatim unless the caller
  opts in via ``include_args_verbatim=True``)
- an Ed25519 signature over the canonical envelope bytes

Receipts can be written one-per-file, or rolled up into an audit
bundle (the format ``verify-artifact --bundle`` consumes natively).
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from aps_delegation import DelegationChain

RECEIPT_TYPE = "adk_tool_call_receipt"
BUNDLE_FORMAT = "scopeblind:audit-bundle:v1"


class _ToolContextLike(Protocol):
    """Structural type for the bits of ``ToolContext`` this module
    touches. Avoids pinning a hard import of ``google.adk`` at module
    load time so tests can pass in fakes."""

    tool_name: str
    args: dict[str, Any]
    invocation_id: str


def _canonicalize(obj: Any) -> str:
    """Canonical JSON matching @veritasacta/artifacts.canonicalize.

    The verifier reproduces the signed bytes by JSON.stringify-ing the
    artifact-minus-signature with a replacer that sorts object keys at
    every level. We mirror that exactly: sorted keys, no whitespace,
    UTF-8 strings preserved (no ASCII escaping). Null values inside
    objects are kept (this is JS object stringify, not the APS-flavor
    canonicalize that drops nulls).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _compute_kid(public_key_hex: str) -> str:
    """RFC 7638 JWK thumbprint of an Ed25519 public key. Matches the
    ``computeKid`` helper in @veritasacta/artifacts."""
    pub = bytes.fromhex(public_key_hex)
    x = _b64url(pub)
    thumbprint_input = '{"crv":"Ed25519","kty":"OKP","x":"' + x + '"}'
    return _b64url(hashlib.sha256(thumbprint_input.encode("utf-8")).digest())


def _public_jwk(public_key_hex: str, kid: str) -> dict[str, str]:
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "kid": kid,
        "x": _b64url(bytes.fromhex(public_key_hex)),
        "use": "sig",
    }


@dataclass
class SignedReceipt:
    """A v2 verify-artifact envelope ready to be written or bundled."""

    envelope: dict[str, Any]
    receipt_id: str
    payload: dict[str, Any] = field(repr=False)

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.envelope, indent=indent, sort_keys=False)

    def write_to(self, directory: str | Path) -> Path:
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{self.receipt_id}.json"
        path.write_text(self.to_json(indent=2))
        return path


def _canonical_args_hash(args: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonicalize(args).encode("utf-8")).hexdigest()


def sign_tool_call(
    tool_context: _ToolContextLike,
    delegation: DelegationChain,
    include_args_verbatim: bool = False,
    issued_at: str | None = None,
) -> SignedReceipt:
    """Produce a signed APS receipt for one ADK tool call.

    The receipt is a v2 envelope per @veritasacta/verify's format. The
    leaf passport's private key (carried on the ``DelegationChain``)
    signs the canonical envelope bytes.
    """
    from agent_passport import sign  # noqa: PLC0415  (lazy SDK import)

    payload: dict[str, Any] = {
        "chain_id": delegation.chain_id,
        "root_agent_id": delegation.root_agent_id,
        "leaf_agent_id": delegation.leaf_agent_id,
        "delegation_id": delegation.delegation_id,
        "scope": list(delegation.scope),
        "tool_name": tool_context.tool_name,
        "invocation_id": tool_context.invocation_id,
        "args_hash": _canonical_args_hash(tool_context.args),
        "timestamp": int(time.time()),
    }
    if include_args_verbatim:
        payload["args"] = tool_context.args

    kid = _compute_kid(delegation.leaf_public_key_hex)
    issued = issued_at or _isoformat_now()

    envelope = {
        "v": 2,
        "type": RECEIPT_TYPE,
        "algorithm": "ed25519",
        "kid": kid,
        "issuer": delegation.leaf_agent_id,
        "issued_at": issued,
        "payload": payload,
    }

    canonical = _canonicalize(envelope)
    signature_hex = sign(canonical, delegation.leaf_private_key_hex)
    envelope["signature"] = signature_hex

    receipt_id = hashlib.sha256(
        canonical.encode("utf-8") + signature_hex.encode()
    ).hexdigest()[:16]

    return SignedReceipt(envelope=envelope, receipt_id=receipt_id, payload=payload)


def write_audit_bundle(
    receipts: list[SignedReceipt],
    delegation: DelegationChain,
    output_path: str | Path,
    issuer: str = "adk-aps-integration",
    description: str | None = None,
) -> Path:
    """Roll a batch of receipts into a verify-artifact audit bundle.

    Bundle shape matches @veritasacta/verify's --bundle format: a top
    level ``verification.signing_keys`` block lets the verifier pick
    the right Ed25519 key per receipt by ``kid``.
    """
    kid = _compute_kid(delegation.leaf_public_key_hex)
    bundle = {
        "format": BUNDLE_FORMAT,
        "generated_at": _isoformat_now(),
        "issuer": issuer,
        "description": description
        or f"ADK tool-call receipts under delegation {delegation.delegation_id}",
        "verification": {
            "signing_keys": [_public_jwk(delegation.leaf_public_key_hex, kid)]
        },
        "receipts": [r.envelope for r in receipts],
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2))
    return path


def _isoformat_now() -> str:
    import datetime as dt

    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
