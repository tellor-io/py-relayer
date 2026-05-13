import getpass
import os
import stat
import sys
from dataclasses import dataclass
from typing import Optional

from chained_accounts import ChainedAccount, find_accounts
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address, to_normalized_address

from src.logger_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedEVMAccount:
    """Account shape used by EVMClient transaction signing."""

    address: str
    key: bytes
    source: str
    _chained_account: Optional[ChainedAccount] = None

    def lock(self) -> None:
        if self._chained_account:
            self._chained_account.lock()


def resolve_evm_account(chain_id: Optional[int] = None) -> ResolvedEVMAccount:
    account_name = _configured_value(os.getenv("EVM_ACCOUNT_NAME"))
    account_address = _configured_value(os.getenv("EVM_ACCOUNT_ADDRESS"))
    keystore_password = _configured_secret(os.getenv("EVM_KEYSTORE_PASSWORD"))

    if account_name or account_address:
        return _resolve_keystore_account(
            name=account_name,
            address=account_address,
            chain_id=chain_id,
            password=keystore_password,
        )

    private_key = _configured_value(os.getenv("ETH_PRIVATE_KEY"))
    if private_key:
        return _resolve_private_key_account(private_key)

    raise RuntimeError(
        "No EVM signer configured. Set EVM_ACCOUNT_NAME/EVM_ACCOUNT_ADDRESS for a keystore "
        "or ETH_PRIVATE_KEY for legacy raw-key signing."
    )


def resolve_evm_account_address(chain_id: Optional[int] = None) -> Optional[str]:
    account_name = _configured_value(os.getenv("EVM_ACCOUNT_NAME"))
    account_address = _configured_value(os.getenv("EVM_ACCOUNT_ADDRESS"))

    if account_name or account_address:
        account = _select_keystore_account(
            name=account_name,
            address=account_address,
            chain_id=chain_id,
        )
        return to_checksum_address(account.address)

    private_key = _configured_value(os.getenv("ETH_PRIVATE_KEY"))
    if private_key:
        return _resolve_private_key_account(private_key).address

    return None


def _configured_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value or (value.startswith("${") and value.endswith("}")):
        return None
    return value


def _configured_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value or (value.strip().startswith("${") and value.strip().endswith("}")):
        return None
    return value


def _resolve_private_key_account(private_key: str) -> ResolvedEVMAccount:
    try:
        local_account: LocalAccount = Account.from_key(private_key)
    except Exception as e:
        raise RuntimeError("Invalid ETH_PRIVATE_KEY") from e

    return ResolvedEVMAccount(
        address=local_account.address,
        key=local_account.key,
        source="ETH_PRIVATE_KEY",
    )


def _resolve_keystore_account(
    *,
    name: Optional[str],
    address: Optional[str],
    chain_id: Optional[int],
    password: Optional[str],
) -> ResolvedEVMAccount:
    account = _select_keystore_account(name=name, address=address, chain_id=chain_id)
    _check_keyfile_permissions(account)
    _unlock_account(account, password)

    return ResolvedEVMAccount(
        address=to_checksum_address(account.address),
        key=account.key,
        source=f"chained-account:{account.name}",
        _chained_account=account,
    )


def _select_keystore_account(
    *,
    name: Optional[str],
    address: Optional[str],
    chain_id: Optional[int],
) -> ChainedAccount:
    if name:
        account = ChainedAccount.get(name)
        if not getattr(account, "_account_json", None):
            raise RuntimeError(f"No chained account found with name '{name}'")
        if chain_id is not None and chain_id not in account.chains:
            raise RuntimeError(f"Chained account '{name}' is not configured for EVM chain {chain_id}")
        if address and account.address.lower() != to_normalized_address(address).lower():
            raise RuntimeError(f"Chained account '{name}' does not match EVM_ACCOUNT_ADDRESS")
    else:
        matches = find_accounts(chain_id=chain_id, address=address)
        if not matches:
            selector = f"address {address}" if address else f"chain {chain_id}"
            raise RuntimeError(f"No chained account found for {selector}")
        if len(matches) > 1:
            names = ", ".join(account.name for account in matches)
            raise RuntimeError(
                "Multiple chained accounts match this EVM signer configuration. "
                f"Set EVM_ACCOUNT_NAME explicitly. Matches: {names}"
            )
        account = matches[0]
    return account


def _unlock_account(account: ChainedAccount, password: Optional[str]) -> None:
    if account.is_unlocked:
        return

    if password is not None:
        try:
            account.unlock(password)
            return
        except ValueError as e:
            raise RuntimeError(f"Invalid password for chained account '{account.name}'") from e

    try:
        account.unlock("")
        return
    except ValueError:
        pass

    if not sys.stdin.isatty():
        raise RuntimeError(
            f"Chained account '{account.name}' requires a password. "
            "Set EVM_KEYSTORE_PASSWORD for non-interactive relayer processes."
        )

    try:
        account.unlock(getpass.getpass(f"Enter password for {account.name} account: "))
    except ValueError as e:
        raise RuntimeError(f"Invalid password for chained account '{account.name}'") from e


def _check_keyfile_permissions(account: ChainedAccount) -> None:
    keyfile = account.keyfile
    if not keyfile.exists():
        raise RuntimeError(f"Chained account keyfile not found for '{account.name}'")

    keyfile_mode = keyfile.stat().st_mode
    if keyfile_mode & (stat.S_IRWXG | stat.S_IRWXO):
        logger.warning(
            "Chained account keyfile %s is accessible by group/other users; "
            "consider chmod 600 for relayer key material.",
            keyfile,
        )

    keystore_dir = keyfile.parent
    dir_mode = keystore_dir.stat().st_mode
    if dir_mode & (stat.S_IWGRP | stat.S_IWOTH):
        logger.warning(
            "Chained account directory %s is writable by group/other users; "
            "consider chmod 700.",
            keystore_dir,
        )
