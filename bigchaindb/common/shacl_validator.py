"""
SHACL Validator Client for BigchainDB

This module provides integration with the SHACL microservice (shacleng)
for declarative transaction validation using RDF and SHACL constraints.
"""

import os
import requests
import logging
import threading
import time
from typing import Dict, Any, Tuple, List, Optional, Set
from bigchaindb import config_utils

logger = logging.getLogger(__name__)


# Marketplace operations that must have a SHACL shape available when SHACL is
# enabled. Startup coverage check refuses to accept transactions for an
# operation whose shape the SHACL service has not loaded.
REQUIRED_SHAPES = frozenset({
    "CREATE", "TRANSFER",
    "ADVERTISEMENT", "UPDATE_ADV",
    "BUY_OFFER", "SELL",
    "REQUEST_RETURN", "SELLER_ACCEPT_RETURN",
})


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class SHACLValidatorClient:
    """
    Client for communicating with the SHACL validation microservice.
    Converts BigchainDB transactions to RDF Turtle format and validates
    them against SHACL shapes.

    Fail policy
    -----------
    When SHACL is enabled the validator is the authoritative semantic layer.
    Any condition that prevents SHACL from reaching a decision (service
    unreachable, request timeout, unloaded shape, malformed response) rejects
    the transaction. Set ``BIGCHAINDB_SHACL_FAIL_OPEN=true`` (or the
    ``shacl.fail_open`` config key) for local development where the operator
    knowingly accepts unvalidated writes; the paper runs it fail-closed.
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
        self.fail_open = _bool_env(
            'BIGCHAINDB_SHACL_FAIL_OPEN',
            shacl_config.get('fail_open', False),
        )
        # Cached, lazily-populated set of shapes that the SHACL service reports
        # as loaded. Populated on first validate() call so the process can boot
        # even if the SHACL service is not yet up.
        self._loaded_shapes: Optional[Set[str]] = None
        self._shapes_lock = threading.Lock()

        if self.enabled:
            mode = "fail-open" if self.fail_open else "fail-closed"
            logger.info(f"SHACL validation enabled ({mode}), endpoint: {self.endpoint}")

    def _fail(self, message: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """Return the correct (conforms, results) tuple for the configured fail policy."""
        if self.fail_open:
            logger.error(f"SHACL fail-open: {message}")
            return True, []
        logger.error(f"SHACL fail-closed: {message}")
        return False, [{"message": message}]

    def _fetch_loaded_shapes(self) -> Optional[Set[str]]:
        """Ask the SHACL service which shapes it has loaded. Returns None on error."""
        try:
            response = requests.get(f'{self.endpoint}/', timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Could not fetch SHACL shape list from {self.endpoint}: {exc}")
            return None
        if response.status_code != 200:
            logger.warning(
                f"SHACL shape list request returned {response.status_code}: {response.text[:200]}"
            )
            return None
        try:
            body = response.json()
        except ValueError as exc:
            logger.warning(f"SHACL shape list returned non-JSON body: {exc}")
            return None
        shapes = body.get('loaded_shapes') or []
        if not isinstance(shapes, list):
            logger.warning(f"SHACL shape list has unexpected shape: {type(shapes).__name__}")
            return None
        return {str(s) for s in shapes}

    def _ensure_shape_coverage(self, operation: str) -> Tuple[bool, Optional[Tuple[bool, List[Dict[str, Any]]]]]:
        """
        Verify the SHACL service has a shape loaded for ``operation``.

        Returns
        -------
        (ok, fail_response):
            ``ok`` is True if coverage is confirmed and the caller should
            proceed. If False, ``fail_response`` is the (conforms, results)
            tuple the caller should return directly.
        """
        with self._shapes_lock:
            if self._loaded_shapes is None:
                self._loaded_shapes = self._fetch_loaded_shapes()
            loaded = self._loaded_shapes

        if loaded is None:
            # Could not reach the shape list. Treat as service unavailable.
            return False, self._fail(
                f"SHACL service {self.endpoint} did not return a shape list; refusing to validate"
            )

        if operation in REQUIRED_SHAPES and operation not in loaded:
            return False, self._fail(
                f"SHACL shape for operation '{operation}' is not loaded (loaded: {sorted(loaded)})"
            )
        return True, None

    def invalidate_shape_cache(self) -> None:
        """Force the next validate() call to re-query the SHACL service's shape list."""
        with self._shapes_lock:
            self._loaded_shapes = None
    
    def validate_transaction(self, tx_dict: Dict[str, Any], requestCreationTimestamp: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validate a transaction against SHACL shapes.
        
        Args:
            tx_dict: Transaction dictionary
            requestCreationTimestamp: Optional timestamp string for metrics logging
            
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

        tx_id = tx_dict.get('id', 'unknown')

        # Startup coverage check: verify the SHACL service actually has a shape
        # loaded for this operation before we spend time serializing RDF.
        ok, fail_response = self._ensure_shape_coverage(operation)
        if not ok:
            return fail_response

        try:
            # Convert transaction to Turtle RDF format (with timing)
            conversion_start = time.time()
            turtle_data = self._convert_to_turtle(tx_dict)
            conversion_time_ms = (time.time() - conversion_start) * 1000
            
            # Log actual conversion time (duration) to metrics
            if requestCreationTimestamp:
                try:
                    from datetime import datetime
                    # Calculate delta from requestCreationTimestamp for context
                    try:
                        request_time = datetime.strptime(requestCreationTimestamp, "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError:
                        try:
                            request_time = datetime.strptime(requestCreationTimestamp, "%Y-%m-%dT%H:%M:%S")
                        except ValueError:
                            # Try with timezone info if present
                            request_time = datetime.fromisoformat(requestCreationTimestamp.replace('Z', '+00:00'))
                    delta_from_request = datetime.now() - request_time
                    metric_logger = logging.getLogger("metrics")
                    # Log: conversion,delta_from_request_ms,operation,tx_id,None,timestamp
                    # Note: conversion_time_ms is the actual duration, but we log delta for consistency with other metrics
                    metric_logger.info(
                        f"conversion,{int(delta_from_request.total_seconds() * 1000)},{operation},{tx_id},None,{time.time()}"
                    )
                    # Also log the actual conversion duration separately
                    metric_logger.info(
                        f"conversion_duration,{int(conversion_time_ms)},{operation},{tx_id},None,{time.time()}"
                    )
                except Exception as e:
                    logger.debug(f"Failed to log conversion metric for {tx_id}: {e}")
            
            logger.debug(f"RDF conversion time: {conversion_time_ms:.3f}ms for {operation} transaction {tx_id}")
            logger.debug(f"RDF Turtle data for {operation} transaction:\n{turtle_data}")
            
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
                # Shape missing at request time. Coverage check should have caught
                # this earlier; invalidate the cache so the next call re-fetches.
                self.invalidate_shape_cache()
                try:
                    available = response.json().get('available_shapes', [])
                except ValueError:
                    available = []
                return self._fail(
                    f"SHACL shape not found for operation '{operation}' (available: {available})"
                )

            else:
                try:
                    error_data = response.json()
                    detail = error_data.get('error', response.text[:200])
                except ValueError:
                    detail = response.text[:200]
                return self._fail(
                    f"SHACL validation request failed with HTTP {response.status_code}: {detail}"
                )

        except requests.exceptions.Timeout:
            return self._fail(f"SHACL validation timeout after {self.timeout}s")

        except requests.exceptions.ConnectionError as exc:
            self.invalidate_shape_cache()
            return self._fail(f"Cannot connect to SHACL service at {self.endpoint}: {exc}")

        except Exception as e:
            logger.error(f"SHACL validation error: {e}", exc_info=True)
            return self._fail(f"Unexpected SHACL validation error: {e}")
    
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
        
        # Add inputs
        inputs = tx_dict.get('inputs', [])
        if inputs:
            turtle += self._serialize_inputs(inputs)
        
        # Add outputs
        outputs = tx_dict.get('outputs', [])
        if outputs:
            turtle += self._serialize_outputs(outputs)
        
        # Remove trailing semicolon and newline, add period
        turtle = turtle.rstrip(';\n') + ' .\n'
        
        return turtle
    
    def _turtle_literals(self, key: str, value: Any, indent: str) -> str:
        """Render a JSON value as one or more Turtle predicate lines."""
        if isinstance(value, bool):
            return f'{indent}bdb:{key} {"true" if value else "false"} ;\n'
        if isinstance(value, str):
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'{indent}bdb:{key} "{escaped}" ;\n'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'{indent}bdb:{key} {value} ;\n'
        if isinstance(value, list):
            lines = ""
            for item in value:
                if isinstance(item, str):
                    lines += self._turtle_literals(key, item, indent)
            return lines
        return ""

    def _serialize_asset(self, asset: Dict[str, Any], operation: str) -> str:
        """Serialize asset field to Turtle."""
        turtle = ""
        
        # For CREATE, asset has 'data' with nested fields
        if operation == 'CREATE' and 'data' in asset:
            asset_data = asset['data']
            turtle += "    bdb:asset [\n"
            turtle += "        bdb:data [\n"
            
            for key, value in asset_data.items():
                turtle += self._turtle_literals(key, value, "            ")
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "        ]\n"
            turtle += "    ] ;\n"
        
        # For UPDATE_ADV, BUY_OFFER, SELL: asset has 'data' with nested fields
        elif operation in ['UPDATE_ADV', 'BUY_OFFER', 'SELL'] and 'data' in asset:
            asset_data = asset['data']
            turtle += "    bdb:asset [\n"
            if 'id' in asset:
                turtle += f'        bdb:id "{asset["id"]}" ;\n'
            turtle += "        bdb:data [\n"
            
            for key, value in asset_data.items():
                turtle += self._turtle_literals(key, value, "            ")
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "        ]\n"
            turtle += "    ] ;\n"
        
        # For ADVERTISEMENT and other operations: asset has 'id' and optional 'data'
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
                    elif isinstance(value, bool):
                        turtle += f'            bdb:{key} {"true" if value else "false"} ;\n'
                turtle = turtle.rstrip(';\n') + '\n'
                turtle += "        ] ;\n"
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += "    ] ;\n"
        
        return turtle
    
    def _serialize_metadata_value(self, key: str, value: Any, indent: str) -> str:
        """Render a metadata value, including nested objects SHACL targets with sh:node."""
        if value is None:
            return ""
        if isinstance(value, dict):
            inner = "".join(
                self._serialize_metadata_value(nested_key, nested_value, indent + "    ")
                for nested_key, nested_value in value.items()
            )
            if inner:
                inner = inner.rstrip(";\n") + "\n"
            return f"{indent}bdb:{key} [\n{inner}{indent}] ;\n"
        if isinstance(value, str) and (
            "timestamp" in key.lower() or "expiry" in key.lower() or key.lower().endswith("date")
        ):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'{indent}bdb:{key} "{escaped}"^^xsd:dateTime ;\n'
        if isinstance(value, float):
            return f'{indent}bdb:{key} "{value}"^^xsd:decimal ;\n'
        return self._turtle_literals(key, value, indent)

    def _serialize_metadata(self, metadata: Dict[str, Any]) -> str:
        """Serialize metadata field to Turtle."""
        turtle = "    bdb:metadata [\n"
        
        # Debug: print metadata to see types
        logger.info(f"DEBUG Metadata: {[(k, type(v).__name__, v) for k, v in metadata.items()]}")
        
        for key, value in metadata.items():
            turtle += self._serialize_metadata_value(key, value, "        ")
        
        turtle = turtle.rstrip(';\n') + '\n'
        turtle += "    ] ;\n"
        
        return turtle
    
    def _serialize_inputs(self, inputs: List[Dict[str, Any]]) -> str:
        """Serialize inputs field to Turtle."""
        turtle = ""
        
        for i, input_obj in enumerate(inputs):
            turtle += f"    bdb:inputs [\n"
            
            # Add fulfillment
            if 'fulfillment' in input_obj:
                turtle += f'        bdb:fulfillment "{input_obj["fulfillment"]}" ;\n'
            
            # Add owners_before
            if 'owners_before' in input_obj:
                owners = input_obj['owners_before']
                if isinstance(owners, list):
                    for owner in owners:
                        turtle += f'        bdb:owners_before "{owner}" ;\n'
                else:
                    turtle += f'        bdb:owners_before "{owners}" ;\n'
            
            # Add fulfills (only if it's not None)
            if 'fulfills' in input_obj and input_obj['fulfills'] is not None:
                fulfills = input_obj['fulfills']
                logger.debug(f"Serializing fulfills: {fulfills}")
                turtle += f'        bdb:fulfills "{fulfills}" ;\n'
            else:
                logger.debug(f"Skipping null/missing fulfills")
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += f"    ] ;\n"
        
        return turtle
    
    def _serialize_outputs(self, outputs: List[Dict[str, Any]]) -> str:
        """Serialize outputs field to Turtle."""
        turtle = ""
        
        for i, output_obj in enumerate(outputs):
            turtle += f"    bdb:outputs [\n"
            
            # Add amount
            if 'amount' in output_obj:
                turtle += f'        bdb:amount "{output_obj["amount"]}" ;\n'
            
            # Add condition
            if 'condition' in output_obj:
                condition = output_obj['condition']
                turtle += f"        bdb:condition [\n"
                
                if 'details' in condition:
                    details = condition['details']
                    turtle += f"            bdb:details [\n"
                    
                    if 'type' in details:
                        turtle += f'                bdb:type "{details["type"]}" ;\n'
                    
                    if 'public_key' in details:
                        turtle += f'                bdb:public_key "{details["public_key"]}" ;\n'
                    
                    turtle = turtle.rstrip(';\n') + '\n'
                    turtle += f"            ] ;\n"
                
                if 'uri' in condition:
                    turtle += f'            bdb:uri "{condition["uri"]}" ;\n'
                
                turtle = turtle.rstrip(';\n') + '\n'
                turtle += f"        ] ;\n"
            
            # Add public_keys
            if 'public_keys' in output_obj:
                public_keys = output_obj['public_keys']
                if isinstance(public_keys, list):
                    for key in public_keys:
                        turtle += f'        bdb:public_keys "{key}" ;\n'
                else:
                    turtle += f'        bdb:public_keys "{public_keys}" ;\n'
            
            turtle = turtle.rstrip(';\n') + '\n'
            turtle += f"    ] ;\n"
        
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

