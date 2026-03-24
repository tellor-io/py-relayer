"""
Compatibility shims for older code expecting eth-abi "single" helpers.

Some older versions of `telliot-feeds` import:
  - `from eth_abi.abi import decode_single, encode_single`
  - `from eth_abi import decode_single`

These helpers are not present in eth-abi v5+. We provide lightweight wrappers
around eth_abi.encode/decode so those imports succeed.
"""

from __future__ import annotations

from typing import Any, Sequence


def ensure_eth_abi_single_helpers() -> None:
    """
    Monkeypatch eth_abi to provide encode_single/decode_single if missing.
    Safe to call multiple times.
    """
    import eth_abi
    import eth_abi.abi as eth_abi_abi

    # Base primitives we wrap
    encode = eth_abi.encode
    decode = eth_abi.decode

    def _as_types(abi_type: str) -> Sequence[str]:
        # eth_abi.encode/decode accept a list/tuple of type strings
        return [abi_type]

    def encode_single(abi_type: str, value: Any) -> bytes:
        return encode(_as_types(abi_type), [value])

    def decode_single(abi_type: str, data: bytes) -> Any:
        out = decode(_as_types(abi_type), data)
        # eth_abi.decode returns a tuple
        return out[0] if isinstance(out, (tuple, list)) and len(out) == 1 else out

    # Patch eth_abi.abi module
    if not hasattr(eth_abi_abi, "encode_single"):
        setattr(eth_abi_abi, "encode_single", encode_single)
    if not hasattr(eth_abi_abi, "decode_single"):
        setattr(eth_abi_abi, "decode_single", decode_single)

    # Patch top-level eth_abi module for `from eth_abi import decode_single`
    if not hasattr(eth_abi, "encode_single"):
        setattr(eth_abi, "encode_single", encode_single)
    if not hasattr(eth_abi, "decode_single"):
        setattr(eth_abi, "decode_single", decode_single)


