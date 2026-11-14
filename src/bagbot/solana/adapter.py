"""Solana on-chain adapter.

RPC calls (connect, balance, blockhash) use plain JSON-RPC over httpx - no
heavy SDK required. Transaction signing for transfers uses the optional
``solders`` package (install with ``pip install bagbot[solana]``).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import httpx

LAMPORTS_PER_SOL = 1_000_000_000


class SolanaError(Exception):
    """Raised when a Solana RPC call fails or signing support is missing."""


@dataclass
class SolanaAdapter:
    """Solana RPC / wallet adapter.

    ``http_client`` may be injected (e.g. with ``httpx.MockTransport``) for
    offline tests.
    """

    rpc_url: str = "https://api.mainnet-beta.solana.com"
    keypair_path: str | None = None
    timeout: float = 30.0
    http_client: httpx.Client | None = None

    def __post_init__(self) -> None:
        self._http = self.http_client or httpx.Client(timeout=self.timeout)
        self._request_id = 0

    # ------------------------------------------------------------------
    # JSON-RPC plumbing
    # ------------------------------------------------------------------
    def _rpc(self, method: str, params: list | None = None):
        self._request_id += 1
        resp = self._http.post(
            self.rpc_url,
            json={"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params or []},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise SolanaError(f"{method} failed: {payload['error']}")
        return payload.get("result")

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def connect(self) -> dict:
        """Verify RPC connectivity; returns the node's version info."""
        return self._rpc("getVersion")

    def get_balance(self, address: str) -> int:
        """Return the lamport balance of ``address``."""
        result = self._rpc("getBalance", [address])
        return int((result or {}).get("value", 0))

    def get_balance_sol(self, address: str) -> float:
        return self.get_balance(address) / LAMPORTS_PER_SOL

    def get_latest_blockhash(self) -> str:
        result = self._rpc("getLatestBlockhash", [{"commitment": "finalized"}])
        return (result or {}).get("value", {}).get("blockhash", "")

    # ------------------------------------------------------------------
    # Transfers (requires solders + a keypair file)
    # ------------------------------------------------------------------
    def _load_keypair(self):
        try:
            from solders.keypair import Keypair  # type: ignore
        except ImportError as exc:
            raise SolanaError(
                "Transfers require the 'solders' package: pip install bagbot[solana]"
            ) from exc
        if not self.keypair_path:
            raise SolanaError("keypair_path is required to sign transactions.")
        with open(self.keypair_path, encoding="utf-8") as fh:
            secret = bytes(json.load(fh))
        return Keypair.from_bytes(secret)

    def transfer(self, to_address: str, lamports: int) -> str:
        """Transfer lamports to ``to_address``; returns the tx signature."""
        if lamports <= 0:
            raise ValueError("lamports must be positive")
        from solders.message import Message  # type: ignore
        from solders.pubkey import Pubkey  # type: ignore
        from solders.system_program import TransferParams, transfer  # type: ignore
        from solders.transaction import Transaction  # type: ignore
        from solders.hash import Hash  # type: ignore

        keypair = self._load_keypair()
        blockhash = Hash.from_string(self.get_latest_blockhash())
        ix = transfer(TransferParams(
            from_pubkey=keypair.pubkey(),
            to_pubkey=Pubkey.from_string(to_address),
            lamports=lamports,
        ))
        msg = Message([ix], keypair.pubkey())
        tx = Transaction([keypair], msg, blockhash)
        return self._rpc(
            "sendTransaction",
            [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64"}],
        )
