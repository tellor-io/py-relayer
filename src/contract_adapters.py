from abc import ABC, abstractmethod
import time

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

class SimpleLayerUserAdapter(ContractAdapter):
    """Adapter for SimpleLayerUser contract"""
    
    def prepare_update_params(self, oracle_data, user_data=None):
        # Extract standard parameters
        attestation_data = oracle_data.get("oracle_attestation_data")
        current_validator_set = oracle_data.get("current_validator_set")
        signatures = oracle_data.get("sigs")
        
        # Add user-specific timestamps
        user_trigger_timestamp = int(time.time())
        begin_relay_timestamp = user_data.get("begin_relay_timestamp", user_trigger_timestamp)
        
        return {
            "attestation_data": attestation_data,
            "current_validator_set": current_validator_set,
            "signatures": signatures,
            "user_trigger_timestamp": user_trigger_timestamp,
            "begin_relay_timestamp": begin_relay_timestamp
        }
    
    def update_oracle_data(self, contract, params):
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
        # Print parameters for debugging
        print(f"TestPriceFeedUserAdapter: Calling updateOracleData2 with params:")
        print(f"  attestation_data: {type(params['attestation_data'])}")
        print(f"  current_validator_set: {type(params['current_validator_set'])}")
        print(f"  signatures: {type(params['signatures'])}")
        print(f"  init_timestamp: {params['init_timestamp']}")
        
        return contract.functions.updateOracleData2(
            params["attestation_data"],
            params["current_validator_set"],
            params["signatures"],
            params["init_timestamp"]
        )

# Factory to get the appropriate adapter
def get_contract_adapter(contract_type):
    adapters = {
        "SimpleLayerUser": SimpleLayerUserAdapter(),
        "TestPriceFeedUser": TestPriceFeedUserAdapter()
    }
    
    return adapters.get(contract_type, None) 