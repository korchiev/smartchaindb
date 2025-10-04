"""
SHACL Validator Client for BigchainDB

This module provides integration with the SHACL microservice (shacleng)
for declarative transaction validation using RDF and SHACL constraints.
"""

import requests
import logging
from typing import Dict, Any, Tuple, List, Optional
from bigchaindb import config_utils

logger = logging.getLogger(__name__)


class SHACLValidatorClient:
    """
    Client for communicating with the SHACL validation microservice.
    Converts BigchainDB transactions to RDF Turtle format and validates
    them against SHACL shapes.
    """
    
    def __init__(self, endpoint: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize the SHACL validator client.
        
        Args:
            endpoint: URL of the SHACL microservice (default from config)
            timeout: HTTP request timeout in seconds (default from config)
        """
        from bigchaindb import config
        
        shacl_config = config.get('shacl', {})
        self.enabled = shacl_config.get('enabled', False)
        self.endpoint = endpoint or shacl_config.get('endpoint', 'http://shacleng:3000')
        self.timeout = timeout or shacl_config.get('timeout', 5)
        
        if self.enabled:
            logger.info(f"SHACL validation enabled, endpoint: {self.endpoint}")
    
    def validate_transaction(self, tx_dict: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate a transaction against SHACL shapes.
        
        Args:
            tx_dict: Transaction dictionary
            
        Returns:
            Tuple of (conforms: bool, results: List[Dict])
            - conforms: True if transaction is valid, False otherwise
            - results: List of validation error/warning messages
        """
        if not self.enabled:
            logger.debug("SHACL validation is disabled, skipping")
            return True, []
        
        operation = tx_dict.get('operation')
        if not operation:
            logger.warning("Transaction missing 'operation' field, cannot validate with SHACL")
            return False, [{"message": "Missing operation field"}]
        
        try:
            # Convert transaction to Turtle RDF format
            turtle_data = self._convert_to_turtle(tx_dict)
            
            # Call SHACL microservice
            response = requests.post(
                f'{self.endpoint}/validate',
                json={
                    'shapeType': operation,
                    'data': turtle_data
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                conforms = result.get('conforms', False)
                results = result.get('results', [])
                
                if not conforms:
                    logger.warning(
                        f"SHACL validation failed for {operation} transaction {tx_dict.get('id', 'unknown')}"
                    )
                    for error in results:
                        logger.debug(f"  - {error.get('message', 'Unknown error')}")
                else:
                    logger.debug(f"SHACL validation passed for {operation} transaction")
                
                return conforms, results
            
            elif response.status_code == 404:
                # Shape not found - log warning but don't fail validation
                error_data = response.json()
                logger.warning(
                    f"SHACL shape not found for operation '{operation}': {error_data.get('error')}"
                )
                logger.debug(f"Available shapes: {error_data.get('available_shapes', [])}")
                # Return True to not block transactions when shape is missing
                return True, []
            
            else:
                logger.error(f"SHACL validation request failed: {response.status_code}")
                error_data = response.json()
                return False, [{"message": error_data.get('error', 'Unknown error')}]
                
        except requests.exceptions.Timeout:
            logger.error(f"SHACL validation timeout after {self.timeout}s")
            return False, [{"message": "SHACL validation timeout"}]
        
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to SHACL service at {self.endpoint}")
            # Don't block transactions if SHACL service is down
            return True, []
        
        except Exception as e:
            logger.error(f"SHACL validation error: {e}", exc_info=True)
            return False, [{"message": str(e)}]
    
    def _convert_to_turtle(self, tx_dict: Dict[str, Any]) -> str:
        """
        Convert a BigchainDB transaction to RDF Turtle format.
        
        Args:
            tx_dict: Transaction dictionary
            
        Returns:
            Transaction serialized as Turtle RDF string
        """
        operation = tx_dict.get('operation', 'UNKNOWN')
        tx_id = tx_dict.get('id', 'unknown')
        version = tx_dict.get('version', '2.0')
        
        # Start Turtle document with prefixes
        turtle = "@prefix bdb: <http://bigchaindb.com/ns#> .\n"
        turtle += "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n"
        
        # Create transaction resource
        turtle += f"<urn:tx:{tx_id}> a bdb:{operation}Transaction ;\n"
        turtle += f'    bdb:operation "{operation}" ;\n'
        turtle += f'    bdb:version "{version}" ;\n'
        
        # Add asset information
        asset = tx_dict.get('asset', {})
        if asset:
            turtle += self._serialize_asset(asset, operation)
        
        # Add metadata
        metadata = tx_dict.get('metadata', {})
        if metadata:
            turtle += self._serialize_metadata(metadata)
        
        # Add inputs count
        inputs = tx_dict.get('inputs', [])
        if inputs:
            turtle += f'    bdb:inputs "{len(inputs)}"^^xsd:integer ;\n'
        
        # Add outputs count
        outputs = tx_dict.get('outputs', [])
        if outputs:
            turtle += f'    bdb:outputs "{len(outputs)}"^^xsd:integer ;\n'
        
        # Remove trailing semicolon and newline, add period
        turtle = turtle.rstrip(';\n') + ' .\n'
        
        return turtle
    
    def _serialize_asset(self, asset: Dict[str, Any], operation: str) -> str:
        """Serialize asset field to Turtle."""
        turtle = ""
        
        # For CREATE, asset has 'data' with nested fields
        if operation == 'CREATE' and 'data' in asset:
            asset_data = asset['data']
            turtle += "    bdb:asset [\n"
            turtle += "        bdb:data [\n"
            
            for key, value in asset_data.items():
                if isinstance(value, str):
                    escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                    turtle += f'            bdb:{key} "{escaped_value}" ;\n'
                elif isinstance(value, (int, float)):
                    turtle += f'            bdb:{key} {value} ;\n'
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "        ]\n"
            turtle += "    ] ;\n"
        
        # For ADVERTISEMENT, BUY_OFFER, SELL: asset has 'id' and optional 'data'
        else:
            turtle += "    bdb:asset [\n"
            
            if 'id' in asset:
                turtle += f'        bdb:id "{asset["id"]}" ;\n'
            
            if 'data' in asset:
                turtle += "        bdb:data [\n"
                for key, value in asset['data'].items():
                    if isinstance(value, str):
                        turtle += f'            bdb:{key} "{value}" ;\n'
                    elif isinstance(value, (int, float)):
                        turtle += f'            bdb:{key} {value} ;\n'
                turtle = turtle.rstrip(';\n') + '\n'
                turtle += "        ] ;\n"
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "    ] ;\n"
        
        return turtle
    
    def _serialize_metadata(self, metadata: Dict[str, Any]) -> str:
        """Serialize metadata field to Turtle."""
        turtle = "    bdb:metadata [\n"
        
        for key, value in metadata.items():
            if isinstance(value, str):
                # Check if it looks like a datetime string
                if 'timestamp' in key.lower() or 'expiry' in key.lower() or 'date' in key.lower():
                    turtle += f'        bdb:{key} "{value}"^^xsd:dateTime ;\n'
                else:
                    escaped_value = value.replace('\\', '\\\\').replace('"', '\\"')
                    turtle += f'        bdb:{key} "{escaped_value}" ;\n'
            elif isinstance(value, int):
                turtle += f'        bdb:{key} {value} ;\n'
            elif isinstance(value, float):
                turtle += f'        bdb:{key} {value} ;\n'
            elif isinstance(value, bool):
                turtle += f'        bdb:{key} {"true" if value else "false"} ;\n'
            elif isinstance(value, (list, dict)):
                # Skip complex nested structures for now
                logger.debug(f"Skipping complex metadata field: {key}")
            elif value is None:
                # Skip null values
                pass
        
        turtle = turtle.rstrip(';\n') + '\n'
        turtle += "    ] ;\n"
        
        return turtle
    
    def health_check(self) -> bool:
        """
        Check if SHACL microservice is available.
        
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.enabled:
            return True
        
        try:
            response = requests.get(f'{self.endpoint}/', timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"SHACL health check failed: {e}")
            return False


# Global singleton instance
_shacl_validator = None


def get_shacl_validator() -> SHACLValidatorClient:
    """
    Get or create the global SHACL validator instance.
    
    Returns:
        SHACLValidatorClient instance
    """
    global _shacl_validator
    if _shacl_validator is None:
        _shacl_validator = SHACLValidatorClient()
    return _shacl_validator

