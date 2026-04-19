"""APS delegation chain setup for Google ADK agents.

A delegation chain is a signed sequence of authority transfers from a
principal passport down to the agent that actually calls tools. Each
link can only narrow the authority above it (monotonic narrowing), so
the chain itself is proof of what the tool-calling agent is allowed to
do.

This module is intentionally separate from the tool-call glue in
``receipt_signing.py``. Set up the chain once per agent; sign per call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class DelegationChain:
    """A resolved APS delegation chain, ready to be referenced by signed
    tool-call receipts.

    ``chain_id`` identifies this chain to a verifier. ``root_agent_id``
    is the passport at the top of the chain (usually the human or the
    service account that owns the ADK agent). ``leaf_agent_id`` is the
    passport whose private key signs tool-call receipts.
    """

    chain_id: str
    root_agent_id: str
    leaf_agent_id: str
    scope: tuple[str, ...]
    spend_limit_usd: float
    delegation_id: str
    leaf_private_key_hex: str
    leaf_public_key_hex: str
    signed_chain_path: Path


def _load_principal_fixture(path: Path) -> dict[str, Any]:
    """Principal fixture shape: ``{"signedPassport": ..., "keyPair":
    {"privateKey": ..., "publicKey": ...}}`` — matches what
    ``agent_passport.create_passport`` returns. Test material only."""
    with path.open() as f:
        data = json.load(f)
    if "signedPassport" not in data or "keyPair" not in data:
        raise ValueError(
            f"{path} is not a valid principal fixture: expected "
            f"keys 'signedPassport' and 'keyPair'"
        )
    return data


def build_delegation_chain(
    principal_passport_path: str | Path,
    agent_scope: Sequence[str],
    spend_limit_usd: float,
    output_dir: str | Path = "delegations",
) -> DelegationChain:
    """Build an APS delegation chain from a principal passport down to
    an ADK tool-calling agent.

    The returned ``DelegationChain`` is what gets referenced by receipts
    signed in ``receipt_signing.sign_tool_call``.

    Args:
        principal_passport_path: Path to the principal (root) passport
            JSON. Must include the private key; delegations have to be
            signed by the issuing party.
        agent_scope: Capability scope to grant the ADK agent. Must be a
            subset of the principal's scope (monotonic narrowing).
        spend_limit_usd: Spend ceiling for this chain in USD. Must be
            less than or equal to any upstream spend limit.
        output_dir: Where to write the signed chain artifact.
    """
    from agent_passport import create_delegation, create_passport, generate_key_pair

    principal = _load_principal_fixture(Path(principal_passport_path))
    principal_passport = principal["signedPassport"]["passport"]
    principal_keys = principal["keyPair"]
    root_agent_id = principal_passport["agentId"]
    principal_pubkey = principal_keys["publicKey"]
    principal_privkey = principal_keys["privateKey"]

    # Fresh session passport for the ADK agent. We let the SDK mint its
    # own keypair, then read it out so receipt_signing can use the
    # private key. Nothing about the leaf is persistent.
    leaf_keys = generate_key_pair()
    leaf_passport_result = create_passport(
        agent_id=f"adk-leaf-{leaf_keys['publicKey'][:12]}",
        agent_name="ADK tool-calling agent (session)",
        owner_alias=principal_passport.get("ownerAlias", "test"),
        mission="Sign tool-call receipts under a narrowed delegation",
        capabilities=list(agent_scope),
        runtime={
            "platform": "python",
            "models": ["adk-agent"],
            "toolsCount": len(agent_scope),
            "memoryType": "session",
        },
    )
    # create_passport always generates its own keypair; rebind to ours
    # so the chain ID matches the keys we hand to the receipt signer.
    leaf_passport_result["keyPair"] = leaf_keys
    leaf_passport_result["signedPassport"]["passport"]["publicKey"] = leaf_keys[
        "publicKey"
    ]
    leaf_agent_id = leaf_passport_result["signedPassport"]["passport"]["agentId"]

    delegation = create_delegation(
        delegated_by=principal_pubkey,
        delegated_to=leaf_keys["publicKey"],
        scope=list(agent_scope),
        private_key=principal_privkey,
        spend_limit=spend_limit_usd,
        max_depth=1,
    )

    chain_id = f"chain_{delegation['delegationId']}"
    out_path = Path(output_dir) / f"{chain_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "chainId": chain_id,
                "principal": principal["signedPassport"],
                "leaf": leaf_passport_result["signedPassport"],
                "delegation": delegation,
            },
            indent=2,
        )
    )

    return DelegationChain(
        chain_id=chain_id,
        root_agent_id=root_agent_id,
        leaf_agent_id=leaf_agent_id,
        scope=tuple(agent_scope),
        spend_limit_usd=spend_limit_usd,
        delegation_id=delegation["delegationId"],
        leaf_private_key_hex=leaf_keys["privateKey"],
        leaf_public_key_hex=leaf_keys["publicKey"],
        signed_chain_path=out_path,
    )
