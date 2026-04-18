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

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# NOTE: imported lazily so the module can be read without the APS SDK
# installed (for example during static docs builds). The concrete
# classes come from ``agent_passport_system`` on PyPI.


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
    signed_chain_path: Path


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
    from agent_passport_system import (  # type: ignore[import-not-found]
        Passport,
        create_delegation,
        resolve_chain,
    )

    principal = Passport.from_file(Path(principal_passport_path))
    leaf = Passport.create()  # fresh session passport for the ADK agent

    delegation = create_delegation(
        delegator=principal,
        delegated_to=leaf.public_key,
        scope=list(agent_scope),
        spend_limit_usd=spend_limit_usd,
    )

    chain = resolve_chain([delegation])
    out_path = Path(output_dir) / f"{chain.chain_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chain.write(out_path)

    return DelegationChain(
        chain_id=chain.chain_id,
        root_agent_id=principal.agent_id,
        leaf_agent_id=leaf.agent_id,
        scope=tuple(agent_scope),
        spend_limit_usd=spend_limit_usd,
        signed_chain_path=out_path,
    )
