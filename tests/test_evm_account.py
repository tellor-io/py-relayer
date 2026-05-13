import os
import unittest
from unittest.mock import patch

from eth_account import Account
from eth_utils import to_checksum_address

from src.evm_account import resolve_evm_account, resolve_evm_account_address


TEST_PRIVATE_KEY = "0x" + "11" * 32


class FakeChainedAccount:
    def __init__(
        self,
        name="relayer",
        address="0x19e7e376e7c213b7e7e7e46cc70a5dd086daff2a",
        chains=None,
        key=TEST_PRIVATE_KEY,
        password="secret",
    ):
        self.name = name
        self.address = address
        self.chains = chains or [11155111]
        self.key = Account.from_key(key).key
        self.password = password
        self.is_unlocked = False
        self._account_json = {"keystore_json": {"address": address[2:]}}

    def unlock(self, password=None):
        if password != self.password:
            raise ValueError("invalid password")
        self.is_unlocked = True

    def lock(self):
        self.is_unlocked = False


class ResolveEVMAccountTests(unittest.TestCase):
    def test_raw_private_key_fallback(self):
        with patch.dict(os.environ, {"ETH_PRIVATE_KEY": TEST_PRIVATE_KEY}, clear=True):
            account = resolve_evm_account(chain_id=11155111)

        expected = Account.from_key(TEST_PRIVATE_KEY)
        self.assertEqual(account.address, expected.address)
        self.assertEqual(account.key, expected.key)
        self.assertEqual(account.source, "ETH_PRIVATE_KEY")

    def test_named_chained_account_unlocks_with_password(self):
        chained_account = FakeChainedAccount(password="secret")
        with patch.dict(
            os.environ,
            {"EVM_ACCOUNT_NAME": "relayer", "EVM_KEYSTORE_PASSWORD": "secret"},
            clear=True,
        ), patch("src.evm_account.ChainedAccount.get", return_value=chained_account), patch(
            "src.evm_account._check_keyfile_permissions"
        ):
            account = resolve_evm_account(chain_id=11155111)

        self.assertTrue(chained_account.is_unlocked)
        self.assertEqual(account.key, Account.from_key(TEST_PRIVATE_KEY).key)
        self.assertEqual(account.source, "chained-account:relayer")

    def test_wrong_chained_account_password_fails(self):
        chained_account = FakeChainedAccount(password="secret")
        with patch.dict(
            os.environ,
            {"EVM_ACCOUNT_NAME": "relayer", "EVM_KEYSTORE_PASSWORD": "wrong"},
            clear=True,
        ), patch("src.evm_account.ChainedAccount.get", return_value=chained_account), patch(
            "src.evm_account._check_keyfile_permissions"
        ):
            with self.assertRaisesRegex(RuntimeError, "Invalid password"):
                resolve_evm_account(chain_id=11155111)

    def test_multiple_auto_discovery_matches_require_name(self):
        accounts = [
            FakeChainedAccount(name="one", password=""),
            FakeChainedAccount(name="two", password=""),
        ]
        with patch.dict(os.environ, {"EVM_ACCOUNT_ADDRESS": accounts[0].address}, clear=True), patch(
            "src.evm_account.find_accounts", return_value=accounts
        ):
            with self.assertRaisesRegex(RuntimeError, "Multiple chained accounts"):
                resolve_evm_account(chain_id=11155111)

    def test_named_account_address_mismatch_fails(self):
        chained_account = FakeChainedAccount(password="")
        with patch.dict(
            os.environ,
            {
                "EVM_ACCOUNT_NAME": "relayer",
                "EVM_ACCOUNT_ADDRESS": "0x0000000000000000000000000000000000000001",
            },
            clear=True,
        ), patch("src.evm_account.ChainedAccount.get", return_value=chained_account):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                resolve_evm_account(chain_id=11155111)

    def test_unresolved_config_placeholders_are_ignored(self):
        with patch.dict(
            os.environ,
            {
                "EVM_ACCOUNT_NAME": "${EVM_ACCOUNT_NAME_1}",
                "ETH_PRIVATE_KEY": TEST_PRIVATE_KEY,
            },
            clear=True,
        ):
            account = resolve_evm_account(chain_id=11155111)

        self.assertEqual(account.address, Account.from_key(TEST_PRIVATE_KEY).address)

    def test_keystore_address_resolution_does_not_unlock(self):
        chained_account = FakeChainedAccount(password="secret")
        with patch.dict(os.environ, {"EVM_ACCOUNT_NAME": "relayer"}, clear=True), patch(
            "src.evm_account.ChainedAccount.get", return_value=chained_account
        ):
            address = resolve_evm_account_address(chain_id=11155111)

        self.assertEqual(address, to_checksum_address(chained_account.address))
        self.assertFalse(chained_account.is_unlocked)


if __name__ == "__main__":
    unittest.main()
