import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.evm_client import EVMClient


class FakeEth:
    def __init__(self):
        self.chain_id = 11155111
        self.block_number = 123
        self.default_account = None


class FakeWeb3:
    eth = None

    class HTTPProvider:
        def __init__(self, url):
            self.url = url

    def __init__(self, provider):
        self.provider = provider
        self.eth = FakeEth()

    def is_connected(self):
        return True


class EVMClientSignerTests(unittest.TestCase):
    def test_init_web3_resolves_signer_after_chain_detection(self):
        resolved_account = SimpleNamespace(
            address="0x0000000000000000000000000000000000000001",
            key=b"key",
            source="test",
        )

        with patch.dict(os.environ, {"WEB3_PROVIDER_URL": "http://localhost:8545"}, clear=True), patch(
            "src.evm_client.Web3", FakeWeb3
        ), patch("src.evm_client.resolve_evm_account", return_value=resolved_account) as resolve:
            client = EVMClient()
            client.init_web3()

        resolve.assert_called_once_with(chain_id=11155111)
        self.assertEqual(client.web3_acct, resolved_account)
        self.assertEqual(client.web3_instance.eth.default_account, resolved_account.address)


if __name__ == "__main__":
    unittest.main()
