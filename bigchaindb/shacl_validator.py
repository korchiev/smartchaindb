# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""
SHACL-based transaction validation for SmartChainDB.

This module provides SHACL (Shapes Constraint Language) validation
for ADVERTISE and BUY transactions, enabling compositional rule design
and batch validation capabilities.
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    from pyshacl import validate
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, XSD
    SHACL_AVAILABLE = True
except ImportError:
    SHACL_AVAILABLE = False
    # Mock classes for when SHACL is not available
    class Graph:
        def __init__(self, *args, **kwargs):
            pass
    class Namespace:
        def __init__(self, *args, **kwargs):
            pass
    class Literal:
        def __init__(self, *args, **kwargs):
            pass
    class URIRef:
        def __init__(self, *args, **kwargs):
            pass
    RDF = None
    XSD = None

from bigchaindb.common.exceptions import ValidationError


@dataclass
class ValidationResult:
    """Result of SHACL validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validation_time: float
    shacl_time: float
    db_fetch_time: float
    rdf_build_time: float


class SHACLValidator:
    """SHACL-based validator for SmartChainDB transactions."""
    
    def __init__(self, bigchaindb_instance):
        """Initialize SHACL validator.
        
        Args:
            bigchaindb_instance: BigchainDB instance for data queries
        """
        if not SHACL_AVAILABLE:
            raise ImportError("SHACL validation requires pyshacl and rdflib packages")
        
        self.bigchaindb = bigchaindb_instance
        self.ns = Namespace("http://smartchaindb.org/ns#")
        self.rdf = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        self.xsd = Namespace("http://www.w3.org/2001/XMLSchema#")
        
        # Load SHACL rules
        self.shacl_rules = self._load_shacl_rules()
        
        # Performance counters
        self.stats = {
            'total_validations': 0,
            'total_db_fetch_time': 0.0,
            'total_rdf_build_time': 0.0,
            'total_shacl_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def _load_shacl_rules(self) -> str:
        """Load SHACL rules for transaction validation."""
        return """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix sc: <http://smartchaindb.org/ns#> .
        
        # ADVERTISE Transaction Rules
        sc:AdvertiseOwnershipRule a sh:NodeShape ;
            sh:targetClass sc:AdvertiseTransaction ;
            sh:sparql [
                sh:select """
                    SELECT ?tx ?assetId ?advertiser ?currentOwner
                    WHERE {
                        ?tx a sc:AdvertiseTransaction ;
                            sc:assetId ?assetId ;
                            sc:advertiser ?advertiser .
                        ?assetId sc:currentOwner ?currentOwner .
                        FILTER (?advertiser != ?currentOwner)
                    }
                """ ;
                sh:message "Advertiser must own the asset being advertised" ;
            ] .
        
        sc:AdvertiseUniquenessRule a sh:NodeShape ;
            sh:targetClass sc:AdvertiseTransaction ;
            sh:sparql [
                sh:select """
                    SELECT ?tx1 ?tx2 ?assetId
                    WHERE {
                        ?tx1 a sc:AdvertiseTransaction ;
                             sc:assetId ?assetId ;
                             sc:status sc:OPEN .
                        ?tx2 a sc:AdvertiseTransaction ;
                             sc:assetId ?assetId ;
                             sc:status sc:OPEN .
                        FILTER (?tx1 != ?tx2)
                    }
                """ ;
                sh:message "Only one open advertisement per asset allowed" ;
            ] .
        
        sc:AdvertiseExpiryRule a sh:NodeShape ;
            sh:targetClass sc:AdvertiseTransaction ;
            sh:property [
                sh:path sc:expiryTime ;
                sh:datatype xsd:dateTime ;
                sh:minInclusive "now"^^xsd:dateTime ;
                sh:message "Advertisement must not be expired" ;
            ] .
        
        sc:AdvertisePriceRule a sh:NodeShape ;
            sh:targetClass sc:AdvertiseTransaction ;
            sh:property [
                sh:path sc:price ;
                sh:datatype xsd:decimal ;
                sh:minInclusive 0 ;
                sh:message "Price must be positive" ;
            ] .
        
        # BUY Transaction Rules
        sc:BuyAdvertisementRule a sh:NodeShape ;
            sh:targetClass sc:BuyTransaction ;
            sh:sparql [
                sh:select """
                    SELECT ?tx ?adId ?adStatus
                    WHERE {
                        ?tx a sc:BuyTransaction ;
                            sc:advertisementId ?adId .
                        ?adId sc:status ?adStatus .
                        FILTER (?adStatus != sc:OPEN)
                    }
                """ ;
                sh:message "Advertisement must exist and be open" ;
            ] .
        
        sc:BuyExpiryRule a sh:NodeShape ;
            sh:targetClass sc:BuyTransaction ;
            sh:sparql [
                sh:select """
                    SELECT ?tx ?adId ?expiryTime
                    WHERE {
                        ?tx a sc:BuyTransaction ;
                            sc:advertisementId ?adId .
                        ?adId sc:expiryTime ?expiryTime .
                        FILTER (?expiryTime < "now"^^xsd:dateTime)
                    }
                """ ;
                sh:message "Advertisement must not be expired" ;
            ] .
        
        sc:BuyPaymentRule a sh:NodeShape ;
            sh:targetClass sc:BuyTransaction ;
            sh:sparql [
                sh:select """
                    SELECT ?tx ?adId ?paymentAmount ?adPrice
                    WHERE {
                        ?tx a sc:BuyTransaction ;
                            sc:advertisementId ?adId ;
                            sc:paymentAmount ?paymentAmount .
                        ?adId sc:price ?adPrice .
                        FILTER (?paymentAmount != ?adPrice)
                    }
                """ ;
                sh:message "Payment amount must match advertisement price" ;
            ] .
        
        # Composed validation rules
        sc:AdvertiseValidation a sh:NodeShape ;
            sh:targetClass sc:AdvertiseTransaction ;
            sh:and (sc:AdvertiseOwnershipRule, sc:AdvertiseUniquenessRule, 
                   sc:AdvertiseExpiryRule, sc:AdvertisePriceRule) .
        
        sc:BuyValidation a sh:NodeShape ;
            sh:targetClass sc:BuyTransaction ;
            sh:and (sc:BuyAdvertisementRule, sc:BuyExpiryRule, sc:BuyPaymentRule) .
        """
    
    def validate_transaction(self, tx: Dict, phase: str = "pre_commit") -> ValidationResult:
        """Validate a single transaction using SHACL.
        
        Args:
            tx: Transaction dictionary
            phase: Validation phase (pre_commit, block_proposal, commit)
            
        Returns:
            ValidationResult with validation status and performance metrics
        """
        start_time = time.time()
        self.stats['total_validations'] += 1
        
        # Convert transaction to RDF
        rdf_start = time.time()
        rdf_graph = self._transaction_to_rdf(tx, phase)
        rdf_time = time.time() - rdf_start
        self.stats['total_rdf_build_time'] += rdf_time
        
        # Apply SHACL validation
        shacl_start = time.time()
        try:
            conforms, report_graph, report_text = validate(
                rdf_graph, 
                shacl_graph=self.shacl_rules,
                inference='rdfs',
                abort_on_first=False,
                allow_warnings=True
            )
            shacl_time = time.time() - shacl_start
            self.stats['total_shacl_time'] += shacl_time
            
            # Parse validation results
            errors = self._parse_validation_errors(report_graph)
            warnings = self._parse_validation_warnings(report_graph)
            
        except Exception as e:
            conforms = False
            errors = [f"SHACL validation error: {str(e)}"]
            warnings = []
            shacl_time = time.time() - shacl_start
            self.stats['total_shacl_time'] += shacl_time
        
        total_time = time.time() - start_time
        
        return ValidationResult(
            is_valid=conforms,
            errors=errors,
            warnings=warnings,
            validation_time=total_time,
            shacl_time=shacl_time,
            db_fetch_time=0.0,  # Will be updated by caller
            rdf_build_time=rdf_time
        )
    
    def validate_batch(self, transactions: List[Dict], phase: str = "pre_commit") -> List[ValidationResult]:
        """Validate multiple transactions in a single SHACL pass.
        
        Args:
            transactions: List of transaction dictionaries
            phase: Validation phase
            
        Returns:
            List of ValidationResult objects
        """
        start_time = time.time()
        self.stats['total_validations'] += len(transactions)
        
        # Convert all transactions to RDF
        rdf_start = time.time()
        rdf_graph = Graph()
        for tx in transactions:
            tx_graph = self._transaction_to_rdf(tx, phase)
            rdf_graph += tx_graph
        rdf_time = time.time() - rdf_start
        self.stats['total_rdf_build_time'] += rdf_time
        
        # Apply SHACL validation
        shacl_start = time.time()
        try:
            conforms, report_graph, report_text = validate(
                rdf_graph,
                shacl_graph=self.shacl_rules,
                inference='rdfs',
                abort_on_first=False,
                allow_warnings=True
            )
            shacl_time = time.time() - shacl_start
            self.stats['total_shacl_time'] += shacl_time
            
            # Parse validation results per transaction
            results = []
            for tx in transactions:
                tx_errors = self._parse_validation_errors_for_transaction(report_graph, tx['id'])
                tx_warnings = self._parse_validation_warnings_for_transaction(report_graph, tx['id'])
                
                results.append(ValidationResult(
                    is_valid=len(tx_errors) == 0,
                    errors=tx_errors,
                    warnings=tx_warnings,
                    validation_time=time.time() - start_time,
                    shacl_time=shacl_time,
                    db_fetch_time=0.0,
                    rdf_build_time=rdf_time
                ))
            
        except Exception as e:
            # If batch validation fails, fall back to individual validation
            results = []
            for tx in transactions:
                result = self.validate_transaction(tx, phase)
                results.append(result)
        
        return results
    
    def _transaction_to_rdf(self, tx: Dict, phase: str) -> Graph:
        """Convert transaction to RDF graph.
        
        Args:
            tx: Transaction dictionary
            phase: Validation phase
            
        Returns:
            RDF graph representation of the transaction
        """
        graph = Graph()
        
        # Add namespaces
        graph.bind("sc", self.ns)
        graph.bind("rdf", self.rdf)
        graph.bind("xsd", self.xsd)
        
        tx_id = URIRef(f"{self.ns}tx_{tx['id']}")
        operation = tx.get('operation', 'UNKNOWN')
        
        # Add transaction type
        if operation == 'ADVERTISE':
            graph.add((tx_id, RDF.type, self.ns.AdvertiseTransaction))
            
            # Add asset ID
            asset_id = tx['asset']['data']['asset_id']
            graph.add((tx_id, self.ns.assetId, URIRef(f"{self.ns}asset_{asset_id}")))
            
            # Add advertiser
            advertiser = tx['inputs'][0]['owners_before'][0]
            graph.add((tx_id, self.ns.advertiser, URIRef(f"{self.ns}key_{advertiser}")))
            
            # Add price
            price = tx['asset']['data'].get('price', '0')
            graph.add((tx_id, self.ns.price, Literal(price, datatype=XSD.decimal)))
            
            # Add expiry time
            expiry_time = tx.get('metadata', {}).get('expiry_time')
            if expiry_time:
                graph.add((tx_id, self.ns.expiryTime, Literal(expiry_time, datatype=XSD.dateTime)))
            
            # Add status
            status = tx.get('metadata', {}).get('status', 'OPEN')
            graph.add((tx_id, self.ns.status, URIRef(f"{self.ns}{status}")))
            
            # Add current owner (from database)
            try:
                asset_tx = self.bigchaindb.get_transaction(asset_id)
                if asset_tx:
                    current_owner = asset_tx.outputs[0].public_keys[0]
                    graph.add((URIRef(f"{self.ns}asset_{asset_id}"), 
                             self.ns.currentOwner, 
                             URIRef(f"{self.ns}key_{current_owner}")))
            except Exception:
                pass  # Skip if asset not found
            
            # Add open advertisements for uniqueness check
            try:
                open_ads = self.bigchaindb.get_open_advertisements_for_asset(asset_id)
                for ad in open_ads:
                    if ad['id'] != tx['id']:  # Exclude current transaction
                        ad_id = URIRef(f"{self.ns}tx_{ad['id']}")
                        graph.add((ad_id, RDF.type, self.ns.AdvertiseTransaction))
                        graph.add((ad_id, self.ns.assetId, URIRef(f"{self.ns}asset_{asset_id}")))
                        graph.add((ad_id, self.ns.status, self.ns.OPEN))
            except Exception:
                pass  # Skip if query fails
        
        elif operation == 'BUY':
            graph.add((tx_id, RDF.type, self.ns.BuyTransaction))
            
            # Add advertisement ID
            ad_id = tx['asset']['data']['advertisement_id']
            graph.add((tx_id, self.ns.advertisementId, URIRef(f"{self.ns}tx_{ad_id}")))
            
            # Add buyer
            buyer = tx['asset']['data']['buyer_public_key']
            graph.add((tx_id, self.ns.buyer, URIRef(f"{self.ns}key_{buyer}")))
            
            # Add payment amount
            payment_amount = tx['asset']['data']['payment_amount']
            graph.add((tx_id, self.ns.paymentAmount, Literal(payment_amount, datatype=XSD.decimal)))
            
            # Add advertisement details (from database)
            try:
                ad_tx = self.bigchaindb.get_transaction(ad_id)
                if ad_tx and ad_tx.operation == 'ADVERTISE':
                    ad_uri = URIRef(f"{self.ns}tx_{ad_id}")
                    graph.add((ad_uri, RDF.type, self.ns.AdvertiseTransaction))
                    
                    # Add advertisement status
                    ad_status = ad_tx.metadata.get('status', 'OPEN')
                    graph.add((ad_uri, self.ns.status, URIRef(f"{self.ns}{ad_status}")))
                    
                    # Add advertisement price
                    ad_price = ad_tx.asset['data'].get('price', '0')
                    graph.add((ad_uri, self.ns.price, Literal(ad_price, datatype=XSD.decimal)))
                    
                    # Add expiry time
                    expiry_time = ad_tx.metadata.get('expiry_time')
                    if expiry_time:
                        graph.add((ad_uri, self.ns.expiryTime, Literal(expiry_time, datatype=XSD.dateTime)))
            except Exception:
                pass  # Skip if advertisement not found
        
        return graph
    
    def _parse_validation_errors(self, report_graph: Graph) -> List[str]:
        """Parse validation errors from SHACL report."""
        errors = []
        for s, p, o in report_graph.triples((None, None, None)):
            if 'ValidationResult' in str(s) and 'message' in str(p):
                errors.append(str(o))
        return errors
    
    def _parse_validation_warnings(self, report_graph: Graph) -> List[str]:
        """Parse validation warnings from SHACL report."""
        warnings = []
        # Similar to errors but for warnings
        return warnings
    
    def _parse_validation_errors_for_transaction(self, report_graph: Graph, tx_id: str) -> List[str]:
        """Parse validation errors for a specific transaction."""
        errors = []
        tx_uri = URIRef(f"{self.ns}tx_{tx_id}")
        for s, p, o in report_graph.triples((None, None, None)):
            if 'ValidationResult' in str(s) and 'message' in str(p):
                # Check if this error is related to the specific transaction
                if str(tx_uri) in str(s) or str(tx_uri) in str(o):
                    errors.append(str(o))
        return errors
    
    def _parse_validation_warnings_for_transaction(self, report_graph: Graph, tx_id: str) -> List[str]:
        """Parse validation warnings for a specific transaction."""
        warnings = []
        # Similar to errors but for warnings
        return warnings
    
    def get_stats(self) -> Dict[str, Any]:
        """Get validation performance statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            'total_validations': 0,
            'total_db_fetch_time': 0.0,
            'total_rdf_build_time': 0.0,
            'total_shacl_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }


class SHACLValidationMiddleware:
    """Middleware for integrating SHACL validation with BigchainDB."""
    
    def __init__(self, bigchaindb_instance, enable_shacl: bool = True):
        """Initialize SHACL validation middleware.
        
        Args:
            bigchaindb_instance: BigchainDB instance
            enable_shacl: Whether to enable SHACL validation
        """
        self.bigchaindb = bigchaindb_instance
        self.enable_shacl = enable_shacl and SHACL_AVAILABLE
        
        if self.enable_shacl:
            self.shacl_validator = SHACLValidator(bigchaindb_instance)
        else:
            self.shacl_validator = None
    
    def validate_transaction(self, tx: Dict, phase: str = "pre_commit") -> Tuple[bool, List[str]]:
        """Validate transaction using both imperative and SHACL validation.
        
        Args:
            tx: Transaction dictionary
            phase: Validation phase
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # First, use existing imperative validation
        try:
            if isinstance(tx, dict):
                tx_obj = self.bigchaindb.models.Transaction.from_dict(tx)
            else:
                tx_obj = tx
            
            tx_obj.validate(self.bigchaindb)
        except Exception as e:
            errors.append(f"Imperative validation failed: {str(e)}")
        
        # Then, use SHACL validation if enabled
        if self.enable_shacl and self.shacl_validator:
            try:
                shacl_result = self.shacl_validator.validate_transaction(tx, phase)
                if not shacl_result.is_valid:
                    errors.extend(shacl_result.errors)
            except Exception as e:
                errors.append(f"SHACL validation failed: {str(e)}")
        
        return len(errors) == 0, errors
    
    def validate_batch(self, transactions: List[Dict], phase: str = "pre_commit") -> List[Tuple[bool, List[str]]]:
        """Validate multiple transactions in batch.
        
        Args:
            transactions: List of transaction dictionaries
            phase: Validation phase
            
        Returns:
            List of (is_valid, error_messages) tuples
        """
        results = []
        
        # Use SHACL batch validation if available
        if self.enable_shacl and self.shacl_validator:
            try:
                shacl_results = self.shacl_validator.validate_batch(transactions, phase)
                for i, shacl_result in enumerate(shacl_results):
                    # Also run imperative validation
                    imperative_valid = True
                    imperative_errors = []
                    
                    try:
                        tx_obj = self.bigchaindb.models.Transaction.from_dict(transactions[i])
                        tx_obj.validate(self.bigchaindb)
                    except Exception as e:
                        imperative_valid = False
                        imperative_errors.append(f"Imperative validation failed: {str(e)}")
                    
                    # Combine results
                    all_errors = imperative_errors + shacl_result.errors
                    results.append((len(all_errors) == 0, all_errors))
                
            except Exception as e:
                # Fall back to individual validation
                for tx in transactions:
                    is_valid, errors = self.validate_transaction(tx, phase)
                    results.append((is_valid, errors))
        else:
            # Use only imperative validation
            for tx in transactions:
                is_valid, errors = self.validate_transaction(tx, phase)
                results.append((is_valid, errors))
        
        return results
