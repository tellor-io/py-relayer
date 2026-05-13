import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from eth_account import Account

from src.cli import cli


TEST_PRIVATE_KEY = "0x" + "22" * 32


class CLIAccountCommandTests(unittest.TestCase):
    def test_add_find_key_and_delete_account(self):
        runner = CliRunner()
        expected_address = Account.from_key(TEST_PRIVATE_KEY).address

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "chained_accounts.base.CHAINED_ACCOUNTS_HOME", Path(tmpdir)
        ), patch("chained_accounts.base.ask_for_password", return_value="secret"), patch("src.cli.load_dotenv"):

            add_result = runner.invoke(
                cli,
                ["account", "add", "relayer-test", TEST_PRIVATE_KEY, "11155111"],
            )
            self.assertEqual(add_result.exit_code, 0, add_result.output)
            self.assertIn("Added new account relayer-test", add_result.output)
            self.assertIn(expected_address.lower(), add_result.output)

            keyfile = Path(tmpdir) / "relayer-test.json"
            self.assertTrue(keyfile.exists())

            find_result = runner.invoke(cli, ["account", "find", "--chain_id", "11155111"])
            self.assertEqual(find_result.exit_code, 0, find_result.output)
            self.assertIn("Found 1 accounts.", find_result.output)
            self.assertIn("Account name: relayer-test", find_result.output)
            self.assertIn(expected_address.lower(), find_result.output)

            key_result = runner.invoke(cli, ["account", "key", "relayer-test", "--password", "secret"])
            self.assertEqual(key_result.exit_code, 0, key_result.output)
            self.assertIn(Account.from_key(TEST_PRIVATE_KEY).key.hex(), key_result.output)

            delete_result = runner.invoke(cli, ["account", "delete", "relayer-test"])
            self.assertEqual(delete_result.exit_code, 0, delete_result.output)
            self.assertFalse(keyfile.exists())

    def test_key_missing_account_reports_like_telliot(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "chained_accounts.base.CHAINED_ACCOUNTS_HOME", Path(tmpdir)
        ), patch("src.cli.load_dotenv"):
            result = runner.invoke(cli, ["account", "key", "missing", "--password", "secret"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Account missing does not exist.", result.output)


if __name__ == "__main__":
    unittest.main()
