"""Full composition: APS delegation + protect-mcp-adk receipts + ADK.

End-to-end walk-through of the three-component agent-governance stack:

    1. build a delegation chain (APS) — the authorization artifact
    2. sign tool calls with protect-mcp-adk's ReceiptSigner — the
       receipt-signing artifact
    3. wrap the receipts in the audit-bundle format @veritasacta/verify
       understands natively
    4. verify with ../../verify.sh at exit 0

The composition's value: two independent keys, two independent parties,
one audit trail. APS's delegation key signs the authorization chain;
protect-mcp-adk's signer signs the per-call receipts. A verifier can
check either independently.

Run with:    python run.py
Verify with: ../../verify.sh receipts/
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aps_delegation import build_delegation_chain  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# protect-mcp-adk on PyPI provides the receipt-signing primitive.
#
# In a real ADK deployment, protect-mcp-adk's ReceiptPlugin hooks into
# after_tool_callback and signs every tool call automatically. The
# plugin wraps ReceiptSigner, which is what actually produces the
# signed bytes. Using ReceiptSigner directly here keeps the example
# runnable without a live ADK runtime and a Gemini API key; the bytes
# produced are identical either way.
# ──────────────────────────────────────────────────────────────────────────────
try:
    from protect_mcp_adk import ReceiptSigner  # type: ignore

    # Access to the internal SigningKey so we can sign the v2 envelope
    # shape that @veritasacta/verify consumes natively. The SigningKey
    # is protect-mcp-adk's underlying PyNaCl key; the same bytes that
    # the plugin uses in a live ADK session.
    from nacl.signing import SigningKey as _NaclSigningKey  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "protect-mcp-adk and PyNaCl are required for this example. Install with:\n"
        "    pip install protect-mcp-adk\n"
        f"Underlying import error: {exc}"
    ) from exc


@dataclass
class FakeToolContext:
    """Minimal shape carrying the fields the receipt layer reads."""

    tool_name: str
    args: dict[str, Any]
    invocation_id: str


def _canonicalize(obj: Any) -> str:
    """Canonical JSON: sorted keys, tight separators, preserve UTF-8.

    Matches the canonicalization @veritasacta/verify uses. A receipt
    is signed over the canonical bytes of the envelope minus the
    signature field, so a verifier reproduces the message bytes by
    running the same canonicalization.
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


def _compute_jwk_thumbprint_kid(public_key_hex: str) -> str:
    """RFC 7638 JWK thumbprint of an Ed25519 public key."""
    pub = bytes.fromhex(public_key_hex)
    x = _b64url(pub)
    thumbprint_input = '{"crv":"Ed25519","kty":"OKP","x":"' + x + '"}'
    return _b64url(hashlib.sha256(thumbprint_input.encode("utf-8")).digest())


def _isoformat_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_signer(fixture_dir: Path) -> "ReceiptSigner":
    """Load a signer from a fixture key file, or generate one.

    Using a fixed key file keeps the example reproducible across CI
    runs: the same signer, the same bundle structure. Delete the
    fixture to run with a fresh random signer.
    """
    key_path = fixture_dir / "agent_key.json"
    if key_path.exists():
        return ReceiptSigner.from_key_file(str(key_path))
    return ReceiptSigner.generate()


def _extract_nacl_signing_key(signer: "ReceiptSigner") -> _NaclSigningKey:
    """Reach into protect-mcp-adk's ReceiptSigner for the underlying
    PyNaCl SigningKey so we can sign the v2 envelope bytes directly.

    protect-mcp-adk stores its key under the ``_signing_key``
    attribute. This private access is intentional for the example: in
    a live ADK deployment the ReceiptPlugin wraps sign_tool_call and we
    never reach under the cover. For the self-contained script we need
    to sign the v2 envelope shape that the bundle format expects,
    which protect-mcp-adk's high-level API does not emit directly.
    """
    signing_key = getattr(signer, "_signing_key", None)
    if signing_key is None:
        # Fallback: some versions name it differently. Try common
        # alternates before failing.
        for attr in ("signing_key", "_key", "key", "_private_key"):
            candidate = getattr(signer, attr, None)
            if candidate is not None:
                signing_key = candidate
                break
    if signing_key is None:
        raise RuntimeError(
            "Could not access ReceiptSigner's underlying SigningKey. "
            "Inspect dir(signer) to find the correct attribute name."
        )
    return signing_key


def _sign_v2_envelope(
    nacl_key: _NaclSigningKey,
    *,
    kid: str,
    issuer: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Sign a v2 verify-artifact envelope.

    The envelope is: {v, type, algorithm, kid, issuer, issued_at,
    payload, signature}. The signature covers the canonical bytes of
    the envelope with signature field removed (but all other fields
    present in sorted order).
    """
    envelope_without_sig = {
        "v": 2,
        "type": "adk_tool_call_receipt",
        "algorithm": "ed25519",
        "kid": kid,
        "issuer": issuer,
        "issued_at": _isoformat_now(),
        "payload": payload,
    }
    canonical = _canonicalize(envelope_without_sig).encode("utf-8")
    signed = nacl_key.sign(canonical)
    signature_hex = signed.signature.hex()
    return {**envelope_without_sig, "signature": signature_hex}


def main() -> None:
    here = Path(__file__).parent
    fixtures = here / "fixtures"
    receipts_dir = here / "receipts"
    receipts_dir.mkdir(exist_ok=True)

    # 1. APS delegation: the authorization artifact.
    #
    # The delegation chain proves the agent is authorized for scope
    # tool:search with a $1.00 spend limit. A verifier walking this
    # chain gets: "this agent was authorized by this principal to do
    # these things." Output lives under delegations/ on disk.
    chain = build_delegation_chain(
        principal_passport_path=here.parent / "basic-tool-call" / "fixtures" / "principal_passport.json",
        agent_scope=["tool:search"],
        spend_limit_usd=1.0,
        output_dir=here / "delegations",
    )
    print(f"[aps] delegation chain: {chain.delegation_id}")

    # 2. protect-mcp-adk signer: the receipt-signing primitive.
    #
    # Two independent keys, two independent signers: APS's delegation
    # key above, protect-mcp-adk's signer here. The tool-call receipts
    # below are signed by protect-mcp-adk's key, not APS's.
    signer = _load_signer(fixtures)
    public_key_hex = signer.public_key_hex  # type: ignore[attr-defined]
    print(f"[protect-mcp-adk] signer public key: {public_key_hex}")
    print(f"[protect-mcp-adk] signer kid: {signer.kid}")  # type: ignore[attr-defined]

    jwk_kid = _compute_jwk_thumbprint_kid(public_key_hex)
    nacl_key = _extract_nacl_signing_key(signer)

    # 3. Simulate two tool calls under the delegation.
    calls = [
        FakeToolContext(
            tool_name="search",
            args={"query": "ADK receipt signing composition", "limit": 3},
            invocation_id="inv-full-0001",
        ),
        FakeToolContext(
            tool_name="search",
            args={"query": "delegation scope and monotonic narrowing", "limit": 5},
            invocation_id="inv-full-0002",
        ),
    ]

    v2_receipts = []
    for call in calls:
        args_hash = "sha256:" + hashlib.sha256(
            _canonicalize(call.args).encode("utf-8")
        ).hexdigest()
        payload = {
            "chain_id": f"chain_{chain.delegation_id}",
            "root_agent_id": chain.root_agent_id,
            "leaf_agent_id": chain.leaf_agent_id,
            "delegation_id": chain.delegation_id,
            "scope": ["tool:search"],
            "tool_name": call.tool_name,
            "invocation_id": call.invocation_id,
            "args_hash": args_hash,
            "timestamp": int(time.time()),
        }
        envelope = _sign_v2_envelope(
            nacl_key,
            kid=jwk_kid,
            issuer=chain.leaf_agent_id,
            payload=payload,
        )
        v2_receipts.append(envelope)

    # 4. Export as the audit-bundle shape @veritasacta/verify consumes.
    bundle = {
        "format": "scopeblind:audit-bundle:v1",
        "generated_at": _isoformat_now(),
        "issuer": "adk-aps-integration",
        "description": (
            f"ADK full-composition example: {len(v2_receipts)} "
            f"protect-mcp-adk receipt(s) under APS delegation "
            f"{chain.delegation_id}"
        ),
        "verification": {
            "signing_keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "kid": jwk_kid,
                    "x": _b64url(bytes.fromhex(public_key_hex)),
                    "use": "sig",
                }
            ]
        },
        "receipts": v2_receipts,
    }

    bundle_path = receipts_dir / "bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"[bundle] {bundle_path} ({len(v2_receipts)} receipt(s))")


if __name__ == "__main__":
    main()
