from src.layer_client import strip_0x
import subprocess

def tip(query_data, layer_address, layer_rpc_endpoint) -> Exception:
    # Remove '0x' prefix if it exists
    query_data_stripped = strip_0x(query_data)
    
    try:
        result = subprocess.run(
            ["layerd", "tx", "oracle", "tip",
             layer_address,  
             query_data_stripped,
             "100000loya", 
             "--from", layer_address, 
             "--chain-id", "layertest-3", 
             "--fees", "5loya", 
             "--keyring-backend", "test", 
             "--yes", 
             "--node=" + layer_rpc_endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        print("Tip result:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error executing tip command:")
        print(f"Exit code: {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise

def request_attestations(query_id, timestamp, layer_address, layer_rpc_endpoint, chain_id="layertest-3") -> Exception:
    try:
        result = subprocess.run(
            ["layerd", "tx", "bridge", "request-attestations",
             layer_address,
             query_id,
             timestamp,
             "--from", layer_address,
             "--chain-id", chain_id,
             "--fees", "5loya",
             "--keyring-backend", "test",
             "--yes",
             "--node=" + layer_rpc_endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        print("Request attestations result:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error executing request attestations command:")
        print(f"Exit code: {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise
