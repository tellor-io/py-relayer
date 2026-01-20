from abc import ABC, abstractmethod
import time
from src.logger_utils import get_logger
from eth_abi import decode

logger = get_logger(__name__)

class ContractAdapter(ABC):
    """Base adapter class for different contract interfaces"""
    
    @abstractmethod
    def prepare_update_params(self, oracle_data, user_data=None):
        """Transform oracle data into contract-specific parameters"""
        pass
    
    @abstractmethod
    def update_oracle_data(self, contract, params):
        """Call the appropriate contract method with transformed parameters"""
        pass

class ReadableContractAdapter(ABC):
    """Mixin interface for contract adapters that can read data from contracts"""
    
    @abstractmethod
    def get_last_relayed_data(self, contract, **kwargs):
        """Get the last relayed data from the contract
        
        Args:
            contract: The contract instance
            
        Returns:
            The raw data from the contract (format depends on contract)
        """
        pass
    
    @abstractmethod 
    def decode_last_relayed_data(self, data):
        """Decode the last relayed data into a standardized format
        
        Args:
            data: The raw data from get_last_relayed_data
            
        Returns:
            dict: Standardized format with keys like 'price', 'timestamp', etc.
        """
        pass

class SimpleLayerUserAdapter(ContractAdapter):
    """Adapter for SimpleLayerUser contract"""
    
    def prepare_update_params(self, oracle_data, user_data=None):
        # Extract standard parameters
        attestation_data = oracle_data.get("oracle_attestation_data")
        current_validator_set = oracle_data.get("current_validator_set")
        signatures = oracle_data.get("sigs")
        
        # Add user-specific timestamps
        begin_relay_timestamp = int(time.time())
        user_trigger_timestamp = user_data.get("user_trigger_timestamp")
        
        return {
            "attestation_data": attestation_data,
            "current_validator_set": current_validator_set,
            "signatures": signatures,
            "user_trigger_timestamp": user_trigger_timestamp,
            "begin_relay_timestamp": begin_relay_timestamp
        }
    
    def update_oracle_data(self, contract, params):
        logger.debug("SimpleLayerUserAdapter: Calling updateOracleData with params:")
        logger.debug(f"  attestation_data: {type(params['attestation_data'])}")
        logger.debug(f"  current_validator_set: {type(params['current_validator_set'])}")
        logger.debug(f"  signatures: {type(params['signatures'])}")
        logger.debug(f"  user_trigger_timestamp: {params['user_trigger_timestamp']}")
        logger.debug(f"  begin_relay_timestamp: {params['begin_relay_timestamp']}")
        return contract.functions.updateOracleData(
            params["attestation_data"],
            params["current_validator_set"],
            params["signatures"],
            params["user_trigger_timestamp"],
            params["begin_relay_timestamp"]
        )

class TestPriceFeedUserAdapter(ContractAdapter):
    """Adapter for TestPriceFeedUser contract"""
    
    def prepare_update_params(self, oracle_data, user_data=None):
        """
        Transform oracle data into TestPriceFeedUser contract parameters
        
        Args:
            oracle_data: The oracle data from the Layer chain
            user_data: Additional user-specific data
        
        Returns:
            dict: The parameters for the updateOracleData2 function
        """
        # Extract standard parameters
        attestation_data = oracle_data.get("oracle_attestation_data")
        current_validator_set = oracle_data.get("current_validator_set")
        signatures = oracle_data.get("sigs")
        
        # Add init timestamp (when the relay was initiated)
        init_timestamp = user_data.get("init_timestamp", int(time.time()))
        
        return {
            "attestation_data": attestation_data,
            "current_validator_set": current_validator_set,
            "signatures": signatures,
            "init_timestamp": init_timestamp
        }
    
    def update_oracle_data(self, contract, params):
        """
        Call the updateOracleData2 function on the TestPriceFeedUser contract
        
        Args:
            contract: The contract instance
            params: The parameters for the function
        
        Returns:
            ContractFunction: The contract function to call
        """
        # Log parameters for debugging
        logger.debug("TestPriceFeedUserAdapter: Calling updateOracleData2 with params:")
        logger.debug(f"  attestation_data: {type(params['attestation_data'])}")
        logger.debug(f"  current_validator_set: {type(params['current_validator_set'])}")
        logger.debug(f"  signatures: {type(params['signatures'])}")
        logger.debug(f"  init_timestamp: {params['init_timestamp']}")
        
        return contract.functions.updateOracleData2(
            params["attestation_data"],
            params["current_validator_set"],
            params["signatures"],
            params["init_timestamp"]
        )

class YoloTellorUserAdapter(ContractAdapter):
    """Adapter for YoloTellorUser contract"""
    
    def prepare_update_params(self, oracle_data, user_data=None):
        """
        Transform oracle data into YoloTellorUser contract parameters
        
        Args:
            oracle_data: The oracle data from the Layer chain
            user_data: Additional user-specific data
        """
       # Extract standard parameters
        attestation_data = oracle_data.get("oracle_attestation_data")
        current_validator_set = oracle_data.get("current_validator_set")
        signatures = oracle_data.get("sigs")
        
        # No user-specific args needed for YoloTellorUser

        return {
            "attestation_data": attestation_data,
            "current_validator_set": current_validator_set,
            "signatures": signatures
        }
    
    def update_oracle_data(self, contract, params):
        """
        Create the updateOracleData function call on the YoloTellorUser contract
        
        Args:
            contract: The contract instance
            params: The parameters for the function
        
        Returns:
            ContractFunction: The contract function to call
        """
        # Log parameters for debugging
        logger.debug("YoloTellorUserAdapter: Calling updateOracleData with params:")
        logger.debug(f"  attestation_data: {type(params['attestation_data'])}")
        logger.debug(f"  current_validator_set: {type(params['current_validator_set'])}")
        logger.debug(f"  signatures: {type(params['signatures'])}")
        
        return contract.functions.updateOracleData(
            params["attestation_data"],
            params["current_validator_set"],
            params["signatures"]
        )
    
class TellorDataBankAdaptor(ContractAdapter, ReadableContractAdapter):
    """Adapter for TellorDataBank contract with read capabilities"""
    
    def prepare_update_params(self, oracle_data, user_data=None):
        """
        Transform oracle data into TellorDataBank contract parameters

        Args:
            oracle_data: The oracle data from the Layer chain
            user_data: Additional user-specific data (none needed)
        """
        # Extract standard parameters
        attestation_data = oracle_data.get("oracle_attestation_data")
        current_validator_set = oracle_data.get("current_validator_set")
        signatures = oracle_data.get("sigs")

        return {
            "attestation_data": attestation_data,
            "current_validator_set": current_validator_set,
            "signatures": signatures
        }
    
    def update_oracle_data(self, contract, params):
        """
        Create the updateOracleData function call on the TellorDataBank contract
        
        Args:
            contract: The contract instance
            params: The parameters for the function
        
        Returns:
            ContractFunction: The contract function to call
        """
        
        return contract.functions.updateOracleData(
            params["attestation_data"],
            params["current_validator_set"],
            params["signatures"]
        )
    
    def get_last_relayed_data(self, contract, query_id):
        """
        Create the getCurrentAggregateData function call on the TellorDataBank contract

        Returns:
            ContractFunction: The contract function to call
        """
        # Get the current aggregate data for the query id
        query_id_bytes = bytes.fromhex(query_id)
        return contract.functions.getCurrentAggregateData(query_id_bytes)
    
    def decode_last_relayed_data(self, data):
        """
        Decode the last relayed data from the TellorDataBank contract

        Args:
            data: The AggregateData struct from getCurrentAggregateData function call

        Returns:
            dict: The decoded data
        """
        # AggregateData struct: (bytes value, uint256 power, uint256 aggregateTimestamp, uint256 attestationTimestamp, uint256 relayTimestamp)
        # data[0] = value (bytes)
        # data[1] = power (uint256) 
        # data[2] = aggregateTimestamp (uint256, in milliseconds)
        # data[3] = attestationTimestamp (uint256, in milliseconds)
        # data[4] = relayTimestamp (uint256, in seconds)
        
        try:
            value_decoded = decode(["uint256"], data[0])  # This is already bytes
            # divide by 10^18 to get the price
            value_int = value_decoded[0] / 10**18
            timestamp_s = int(data[2]) / 1000  # aggregateTimestamp in seconds
            relay_timestamp_s = int(data[4])

            return {
                    "value": [value_int],  # Wrap in list to match expected format in price comparison
                    "timestamp": timestamp_s,
                    "relay_timestamp": relay_timestamp_s 
                }
        except Exception as e:
            logger.error(f"Error decoding last relayed data: {e}")
            return None

# Factory to get the appropriate adapter
def get_contract_adapter(contract_type):
    adapters = {
        "SimpleLayerUser": SimpleLayerUserAdapter(),
        "TestPriceFeedUser": TestPriceFeedUserAdapter(),
        "YoloTellorUser": YoloTellorUserAdapter(),
        "TellorDataBank": TellorDataBankAdaptor()
    }
    
    return adapters.get(contract_type, None)

# Utility functions for adapter capabilities
def adapter_can_read_data(adapter):
    """Check if an adapter supports reading data from contracts
    
    Args:
        adapter: The contract adapter instance
        
    Returns:
        bool: True if the adapter can read data, False otherwise
    """
    return isinstance(adapter, ReadableContractAdapter)

def get_last_relayed_data_if_supported(adapter, contract):
    """Get last relayed data if the adapter supports it
    
    Args:
        adapter: The contract adapter instance
        contract: The contract instance
        
    Returns:
        dict or None: The decoded data if supported, None otherwise
    """
    if adapter_can_read_data(adapter):
        raw_data = adapter.get_last_relayed_data(contract)
        return adapter.decode_last_relayed_data(raw_data)
    return None 