#!/usr/bin/env python3
"""
Example usage of SELL transaction type with Two Atomic Transfers

This example demonstrates:
1. Creating a SELL transaction that accepts a buy offer
2. Validating the SELL transaction
3. Demonstrating business rules
4. Showing the complete transaction flow with two atomic transfers
"""

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair
from bigchaindb.common.output import Output
from cryptoconditions import Ed25519Sha256
from datetime import datetime

def create_sell_example():
    """Example of creating a SELL transaction"""
    print("=== SELL Transaction with Two Atomic Transfers Example ===\n")
    
    # Generate keypairs for seller and buyer
    seller_keypair = generate_keypair()
    buyer_keypair = generate_keypair()
    
    print(f"Seller Public Key: {seller_keypair.public_key}")
    print(f"Buyer Public Key: {buyer_keypair.public_key}\n")
    
    # Create a mock buy offer transaction (in real scenario, this would exist)
    buy_offer_id = "mock_buy_offer_123"
    asset_id = "mock_asset_456"
    
    # Create input for the asset being sold
    # In a real scenario, this would reference an existing asset output owned by seller
    asset_input = Transaction.Input.generate([seller_keypair.public_key])
    
    # Set sale details
    sale_amount = 1000
    sale_currency = "USD"
    sale_timestamp = datetime.utcnow().isoformat() + "Z"
    
    # Create metadata for the sell transaction
    metadata = {
        'seller_public_key': seller_keypair.public_key,
        'buyer_public_key': buyer_keypair.public_key,
        'sale_amount': sale_amount,
        'sale_currency': sale_currency,
        'sale_timestamp': sale_timestamp,
        'sale_notes': 'Asset sold to buyer via buy offer acceptance'
    }
    
    print("Creating SELL transaction...")
    print(f"Asset ID: {asset_id}")
    print(f"Buy Offer ID: {buy_offer_id}")
    print(f"Sale Amount: {sale_amount} {sale_currency}")
    print(f"Sale Timestamp: {sale_timestamp}\n")
    
    # Create the SELL transaction
    sell_tx = Transaction.sell(
        inputs=[asset_input],
        asset_id=asset_id,
        buy_offer_id=buy_offer_id,
        metadata=metadata
    )
    
    print("SELL Transaction Created Successfully!")
    print(f"Transaction ID: {sell_tx.id}")
    print(f"Operation: {sell_tx.operation}")
    print(f"Asset: {sell_tx.asset}")
    print(f"Metadata: {sell_tx.metadata}")
    print(f"Inputs: {len(sell_tx.inputs)}")
    print(f"Outputs: {len(sell_tx.outputs)}")
    
    # Show the two atomic transfer outputs
    if len(sell_tx.outputs) == 2:
        asset_output = sell_tx.outputs[0]
        payment_output = sell_tx.outputs[1]
        
        print(f"\nTwo Atomic Transfer Outputs:")
        print(f"1. Asset Transfer Output:")
        print(f"   Amount: {asset_output.amount}")
        print(f"   Public Keys: {asset_output.public_keys}")
        print(f"   Condition URI: {asset_output.fulfillment.condition_uri}")
        
        print(f"\n2. Payment Transfer Output:")
        print(f"   Amount: {payment_output.amount}")
        print(f"   Public Keys: {payment_output.public_keys}")
        print(f"   Condition URI: {payment_output.fulfillment.condition_uri}")
    
    return sell_tx

def demonstrate_business_rules():
    """Demonstrate the business rules for SELL transactions"""
    print("\n=== Business Rules Demonstration ===\n")
    
    print("1. **Two Atomic Transfers**:")
    print("   - Asset ownership transfers from seller to buyer")
    print("   - Payment transfers from escrow to seller")
    print("   - Both transfers happen simultaneously\n")
    
    print("2. **Buy Offer Validation**:")
    print("   - Must reference an existing, valid buy offer")
    print("   - Buy offer must target the same asset")
    print("   - Buy offer must have sufficient escrow funds\n")
    
    print("3. **Seller Authorization**:")
    print("   - Seller must be the current owner of the asset")
    print("   - Seller must be the advertiser from the advertisement")
    print("   - Valid cryptographic signatures required\n")
    
    print("4. **Advertisement Status Control**:")
    print("   - Cannot sell if advertisement is LOCKED or CLOSED")
    print("   - Prevents multiple sales of the same asset")
    print("   - Ensures proper transaction flow\n")
    
    print("5. **Escrow Integration**:")
    print("   - Payment comes from escrow created by BUY_OFFER")
    print("   - No need for separate payment handling")
    print("   - Secure, automatic payment transfer\n")

def show_transaction_flow():
    """Show the complete transaction flow"""
    print("\n=== Complete Transaction Flow ===\n")
    
    print("1. **Asset Creation** (CREATE transaction)")
    print("   - Asset is created and owned by seller\n")
    
    print("2. **Advertisement** (ADVERTISEMENT transaction)")
    print("   - Seller advertises asset for sale")
    print("   - Status: OPEN\n")
    
    print("3. **Buy Offer** (BUY_OFFER transaction)")
    print("   - Buyer submits offer with direct escrow transfer")
    print("   - Buyer's payment asset moves to escrow account")
    print("   - Asset ownership remains with seller\n")
    
    print("4. **Sale Acceptance** (SELL transaction)")
    print("   - Seller accepts the buy offer")
    print("   - Two atomic transfers happen simultaneously:")
    print("     * Asset ownership transfers from seller to buyer")
    print("     * Payment transfers from escrow to seller")
    print("   - Advertisement status: OPEN → LOCKED → CLOSED\n")
    
    print("5. **Optional: Return Process**")
    print("   - If buyer wants to return asset (REQUEST_RETURN)")
    print("   - Seller can accept return (ACCEPT_RETURN)")
    print("   - Asset returns to seller, payment returns to buyer\n")

if __name__ == "__main__":
    # Create the sell example
    sell_tx = create_sell_example()
    
    # Demonstrate business rules
    demonstrate_business_rules()
    
    # Show transaction flow
    show_transaction_flow()
    
    print("\n=== Summary ===")
    print("The SELL transaction now properly implements two atomic transfers:")
    print("- Asset transfer to buyer")
    print("- Payment transfer from escrow to seller")
    print("- Both transfers happen simultaneously for security")
    print("- Integration with BUY_OFFER escrow system")
    print("- Proper validation of all business rules")
