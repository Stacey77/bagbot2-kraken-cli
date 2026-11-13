"""Stub adapter defining the interface for future Solana wallet/on-chain ops.

Intentionally raises :class:`NotImplementedError` - the Kraken CLI is the
priority for this first pass; this module only fixes the integration point.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SolanaAdapter:
    """Interface for Solana RPC / wallet operations (not yet implemented)."""

    rpc_url: str = "https://api.mainnet-beta.solana.com"
    keypair_path: str | None = None

    def connect(self) -> None:
        """Establish an RPC connection and load the wallet keypair."""
        raise NotImplementedError("Solana support is not implemented yet.")

    def get_balance(self, address: str) -> int:
        """Return the lamport balance of ``address``."""
        raise NotImplementedError("Solana support is not implemented yet.")

    def transfer(self, to_address: str, lamports: int) -> str:
        """Transfer lamports to ``to_address``; returns the tx signature."""
        raise NotImplementedError("Solana support is not implemented yet.")
