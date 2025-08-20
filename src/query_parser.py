import json
import os
import re
from typing import Dict, List, Tuple, Any, Optional
from eth_abi import encode
from web3 import Web3
from src.logger_utils import get_logger

logger = get_logger(__name__)

class QueryParser:
    """Parser for Tellor query strings that generates queryData and queryId"""
    
    def __init__(self, query_types_dir: str = "query-types"):
        self.query_types_dir = query_types_dir
        self.query_types_cache = {}
        self._load_query_types()
    
    def _load_query_types(self):
        """Load all query type definitions from JSON files"""
        if not os.path.exists(self.query_types_dir):
            logger.warning(f"Query types directory {self.query_types_dir} not found")
            return
            
        for filename in os.listdir(self.query_types_dir):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(self.query_types_dir, filename)
                    with open(filepath, 'r') as f:
                        query_type_def = json.load(f)
                        query_type_name = query_type_def.get('type')
                        if query_type_name:
                            self.query_types_cache[query_type_name] = query_type_def
                            logger.debug(f"Loaded query type: {query_type_name}")
                except Exception as e:
                    logger.error(f"Error loading query type from {filename}: {e}")
    
    def parse_query_string(self, query_string: str) -> Tuple[bytes, bytes]:
        """
        Parse a query string and return (queryData, queryId)
        
        Supports formats:
        - SpotPrice(eth,usd) - using predefined query type
        - CustomType(uint256 123, string 'hello', bytes32 0x...) - with explicit types
        
        Args:
            query_string: The query string to parse
            
        Returns:
            Tuple of (queryData, queryId)
        """
        # parse the query string format: QueryType(arg1, arg2, ...)
        match = re.match(r'^(\w+)\((.*)\)$', query_string.strip())
        if not match:
            raise ValueError(f"Invalid query string format: {query_string}")
        
        query_type_name = match.group(1)
        args_string = match.group(2).strip()
        
        logger.info(f"Parsing query string: {query_type_name}({args_string})")
        
        # check if we have a predefined query type
        if query_type_name in self.query_types_cache:
            query_data_args, query_data = self._parse_known_query_type(
                query_type_name, args_string
            )
        else:
            query_data_args, query_data = self._parse_unknown_query_type(
                query_type_name, args_string
            )
        
        # generate queryId as keccak256(queryData)
        query_id = Web3.keccak(query_data)
        
        logger.info(f"Generated queryId: {query_id.hex()}")
        logger.debug(f"Generated queryData: 0x{query_data.hex()}")
        
        return query_data, query_id
    
    def _parse_known_query_type(self, query_type_name: str, args_string: str) -> Tuple[bytes, bytes]:
        """Parse a query string using a known query type definition"""
        query_type_def = self.query_types_cache[query_type_name]
        abi_def = query_type_def['abi']
        
        # check if args_string contains type annotations (like "string eth, string usd")
        # if so, extract just the values
        if self._has_inline_types(args_string):
            logger.debug("Detected inline types in known query type, extracting values only")
            typed_args = self._parse_typed_args(args_string)
            # extract just the values, ignoring the types since we have the definition
            args = [arg_value for _, arg_value in typed_args]
        else:
            # parse simple comma-separated arguments
            args = self._parse_simple_args(args_string)
        
        if len(args) != len(abi_def):
            raise ValueError(f"Expected {len(abi_def)} arguments for {query_type_name}, got {len(args)}")
        
        # convert arguments to proper types and encode
        converted_args = []
        arg_types = []
        
        for i, (arg_value, arg_def) in enumerate(zip(args, abi_def)):
            arg_type = arg_def['type']
            converted_value = self._convert_argument(arg_value, arg_type)
            converted_args.append(converted_value)
            arg_types.append(arg_type)
        
        # encode the arguments
        query_data_args = encode(arg_types, converted_args)
        
        # encode the full queryData: abi.encode(queryTypeName, queryDataArgs)
        query_data = encode(['string', 'bytes'], [query_type_name, query_data_args])
        
        return query_data_args, query_data
    
    def _parse_unknown_query_type(self, query_type_name: str, args_string: str) -> Tuple[bytes, bytes]:
        """Parse a query string with explicit type annotations"""
        # parse arguments with explicit types: "uint256 123, string 'hello', bytes32 0x..."
        args = self._parse_typed_args(args_string)
        
        converted_args = []
        arg_types = []
        
        for arg_type, arg_value in args:
            converted_value = self._convert_argument(arg_value, arg_type)
            converted_args.append(converted_value)
            arg_types.append(arg_type)
        
        # encode the arguments
        query_data_args = encode(arg_types, converted_args)
        
        # encode the full queryData: abi.encode(queryTypeName, queryDataArgs)
        query_data = encode(['string', 'bytes'], [query_type_name, query_data_args])
        
        return query_data_args, query_data
    
    def _parse_simple_args(self, args_string: str) -> List[str]:
        """Parse simple comma-separated arguments"""
        if not args_string.strip():
            return []
        
        # simple split by comma (doesn't handle quoted strings with commas)
        args = [arg.strip() for arg in args_string.split(',')]
        return args
    
    def _parse_typed_args(self, args_string: str) -> List[Tuple[str, str]]:
        """Parse arguments with explicit type annotations"""
        if not args_string.strip():
            return []
        
        args = []
        # regex to match: type value, type value, ...
        # handles quoted strings and hex values
        pattern = r'(\w+(?:\[\])?)\s+((?:\'[^\']*\'|"[^"]*"|0x[0-9a-fA-F]+|\w+))'
        
        for match in re.finditer(pattern, args_string):
            arg_type = match.group(1)
            arg_value = match.group(2)
            if arg_type:  # ensure arg_type is not None
                args.append((arg_type, arg_value))
        
        return args
    
    def _has_inline_types(self, args_string: str) -> bool:
        """Check if the arguments string contains inline type annotations"""
        # look for patterns like "type value" where type is a common solidity type
        type_pattern = r'\b(uint\d*|int\d*|string|bool|address|bytes\d*)\s+'
        return bool(re.search(type_pattern, args_string.strip()))
    
    def _convert_argument(self, value: str, arg_type: str) -> Any:
        """Convert a string argument to the appropriate Python type for ABI encoding"""
        value = value.strip()
        
        # remove quotes from strings
        if arg_type == 'string' and ((value.startswith("'") and value.endswith("'")) or 
                                     (value.startswith('"') and value.endswith('"'))):
            return value[1:-1]
        
        # handle bytes and bytes32
        if arg_type.startswith('bytes'):
            if value.startswith('0x'):
                return bytes.fromhex(value[2:])
            else:
                # treat as string and encode to bytes
                return value.encode('utf-8')
        
        # handle integers
        if arg_type.startswith('uint') or arg_type.startswith('int'):
            return int(value)
        
        # handle addresses
        if arg_type == 'address':
            if not value.startswith('0x'):
                value = '0x' + value
            return value
        
        # handle booleans
        if arg_type == 'bool':
            return value.lower() in ('true', '1', 'yes')
        
        # default: return as string
        return value
    
    def get_query_info(self, query_string: str) -> Dict[str, Any]:
        """
        Get complete query information including queryData, queryId, and metadata
        
        Args:
            query_string: The query string to parse
            
        Returns:
            Dictionary with queryData, queryId, queryType, arguments info, and other metadata
        """
        # extract query type name and args string first
        match = re.match(r'^(\w+)\((.*)\)$', query_string.strip())
        if not match:
            raise ValueError(f"Invalid query string format: {query_string}")
        
        query_type_name = match.group(1)
        args_string = match.group(2).strip()
        
        # parse arguments to get the info
        parsed_args = self._parse_arguments_info(query_type_name, args_string)
        
        # then parse normally for queryData and queryId
        query_data, query_id = self.parse_query_string(query_string)
        
        return {
            'queryData': '0x' + query_data.hex(),
            'queryId': query_id.hex(),  # query_id.hex() already includes 0x prefix
            'queryType': query_type_name,
            'queryString': query_string,
            'hasDefinition': query_type_name in self.query_types_cache,
            'arguments': parsed_args
        }
    
    def _parse_arguments_info(self, query_type_name: str, args_string: str) -> List[Dict[str, Any]]:
        """Parse arguments and return structured info about each argument"""
        if not args_string.strip():
            return []
        
        parsed_args = []
        
        if query_type_name in self.query_types_cache:
            # known query type
            query_type_def = self.query_types_cache[query_type_name]
            abi_def = query_type_def['abi']
            
            if self._has_inline_types(args_string):
                # inline types provided, extract values only
                typed_args = self._parse_typed_args(args_string)
                args = [arg_value for _, arg_value in typed_args]
            else:
                # simple args
                args = self._parse_simple_args(args_string)
            
            for i, (arg_value, arg_def) in enumerate(zip(args, abi_def)):
                arg_type = arg_def['type']
                arg_name = arg_def.get('name', f'arg{i+1}')
                converted_value = self._convert_argument(arg_value, arg_type)
                
                parsed_args.append({
                    'name': arg_name,
                    'type': arg_type,
                    'rawValue': arg_value,
                    'convertedValue': converted_value
                })
        else:
            # unknown query type with explicit types
            typed_args = self._parse_typed_args(args_string)
            
            for i, (arg_type, arg_value) in enumerate(typed_args):
                converted_value = self._convert_argument(arg_value, arg_type)
                
                parsed_args.append({
                    'name': f'arg{i+1}',
                    'type': arg_type,
                    'rawValue': arg_value,
                    'convertedValue': converted_value
                })
        
        return parsed_args


def parse_query_string(query_string: str) -> Tuple[str, str]:
    """
    Convenience function to parse a query string and return hex-encoded queryData and queryId
    
    Args:
        query_string: The query string to parse
        
    Returns:
        Tuple of (queryData_hex, queryId_hex)
    """
    parser = QueryParser()
    query_data, query_id = parser.parse_query_string(query_string)
    return '0x' + query_data.hex(), query_id.hex()  # query_id.hex() already includes 0x prefix


if __name__ == "__main__":
    # test the parser
    parser = QueryParser()
    
    # test known query type
    try:
        query_data, query_id = parser.parse_query_string("SpotPrice(eth,usd)")
        print(f"SpotPrice(eth,usd):")
        print(f"  queryData: 0x{query_data.hex()}")
        print(f"  queryId: 0x{query_id.hex()}")
    except Exception as e:
        print(f"Error parsing SpotPrice: {e}")
    
    # test unknown query type with explicit types
    try:
        query_data, query_id = parser.parse_query_string("CustomType(uint256 123, string 'hello world')")
        print(f"\nCustomType(uint256 123, string 'hello world'):")
        print(f"  queryData: 0x{query_data.hex()}")
        print(f"  queryId: 0x{query_id.hex()}")
    except Exception as e:
        print(f"Error parsing CustomType: {e}") 