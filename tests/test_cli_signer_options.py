import unittest
from unittest.mock import patch

from click.testing import CliRunner

from src.cli import cli


class CLISignerOptionTests(unittest.TestCase):
    def test_relay_threshold_accepts_keystore_without_raw_private_key(self):
        runner = CliRunner()
        args = [
            "relay-threshold",
            "--query-id",
            "0x" + "00" * 32,
            "--query-data",
            "0x1234",
            "--price-threshold",
            "0.02",
            "--evm-account-name",
            "relayer",
            "--data-bridge-address",
            "0x0000000000000000000000000000000000000001",
            "--layer-user-address",
            "0x0000000000000000000000000000000000000002",
            "--evm-network",
            "sepolia",
            "--layer-swagger",
            "http://layer",
            "--layer-rpc",
            "http://layer-rpc",
            "--layer-tx-creator-address",
            "tellor1relayer",
        ]

        with patch("src.cli.start_primary_threshold_relayer") as start_relayer:
            result = runner.invoke(cli, args, env={"ETH_PRIVATE_KEY": ""})

        self.assertEqual(result.exit_code, 0, result.output)
        start_relayer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
