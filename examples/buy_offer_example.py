#!/usr/bin/env python3
"""
Example usage of BUY_OFFER transaction type with Direct Escrow Transfer

This example demonstrates:
1. Creating a buy offer with direct escrow transfer
2. Validating the buy offer
3. Demonstrating business rules
4. Showing the complete transaction flow with integrated escrow
"""

from bigchaindb.common.transaction import Transaction
from bigchaindb.common.crypto import generate_keypair
from bigchaindb.common.output import Output
from cryptoconditions import Ed25519Sha256
from datetime import datetime, timedelta

def create_buy_offer_with_direct_escrow_example():
    """Example of creating a BUY_OFFER transaction with direct escrow transfer"""
    print("=== BUY_OFFER Transaction with Direct Escrow Transfer Example ===\n")
    
    # Generate keypairs for buyer, seller, and escrow
    buyer_keypair = generate_keypair()
    seller_keypair = generate_keypair()
    escrow_keypair = generate_keypair()
    
    print(f"Buyer Public Key: {buyer_keypair.public_key}")
    print(f"Seller Public Key: {seller_keypair.public_key}")
    print(f"Escrow Public Key: {escrow_keypair.public_key}\n")
    
    # Create a mock advertisement transaction (in real scenario, this would exist)
    advertisement_id = "mock_advertisement_123"
    asset_id = "mock_asset_456"
    
    # Create input for the asset being offered for
    # In a real scenario, this would reference an existing asset output
    asset_input = Transaction.Input.generate([buyer_keypair.public_key])
    
    # Set offer details
    offer_amount = 1000
    offer_currency = "USD"
    offer_timestamp = datetime.utcnow().isoformat() + "Z"
    offer_expiry = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    
    # Create metadata for the buy offer
    metadata = {
        'buyer_public_key': buyer_keypair.public_key,
        'offer_amount': offer_amount,
        'offer_currency': offer_currency,
        'offer_timestamp': offer_timestamp,
        'offer_expiry': offer_expiry,
        'escrow_public_key': escrow_keypair.public_key,
        'offer_notes': 'Interested in purchasing this asset'
    }
    
    print("Creating BUY_OFFER transaction...")
    print(f"Asset ID: {asset_id}")
    print(f"Advertisement ID: {advertisement_id}")
    print(f"Offer Amount: {offer_amount} {offer_currency}")
    print(f"Offer Expiry: {offer_expiry}")
    print(f"Escrow Account: {escrow_keypair.public_key}\n")
    
    # Create the BUY_OFFER transaction
    buy_offer_tx = Transaction.buy_offer(
        inputs=[asset_input],
        asset_id=asset_id,
        advertisement_id=advertisement_id,
        metadata=metadata
    )
    
    print("BUY_OFFER Transaction Created Successfully!")
    print(f"Transaction ID: {buy_offer_tx.id}")
    print(f"Operation: {buy_offer_tx.operation}")
    print(f"Asset: {buy_offer_tx.asset}")
    print(f"Metadata: {buy_offer_tx.metadata}")
    print(f"Inputs: {len(buy_offer_tx.inputs)}")
    print(f"Outputs: {len(buy_offer_tx.outputs)}")
    
    # Show the escrow output
    if buy_offer_tx.outputs:
        escrow_output = buy_offer_tx.outputs[0]
        print(f"\nEscrow Output:")
        print(f"  Amount: {escrow_output.amount}")
        print(f"  Public Keys: {escrow_output.public_keys}")
        print(f"  Condition URI: {escrow_output.fulfillment.condition_uri}")
    
    return buy_offer_tx

def demonstrate_business_rules():
    """Demonstrate the business rules for BUY_OFFER transactions"""
    print("\n=== Business Rules Demonstration ===\n")
    
    print("1. **Direct Escrow Transfer**:")
    print("   - Buyer's payment asset is directly transferred to escrow")
    print("   - No separate escrow transaction required")
    print("   - Atomic operation: offer + escrow in one transaction\n")
    
    print("2. **Asset Ownership Validation**:")
    print("   - Buyer must own the asset being offered for")
    print("   - Asset ownership is verified through input validation\n")
    
    print("3. **Advertisement Reference**:")
    print("   - Must reference an existing OPEN advertisement")
    print("   - Ensures the asset is actually for sale\n")
    
    print("4. **Anti-Self-Bidding**:")
    print("   - Buyer cannot be the same as advertiser")
    print("   - Prevents circular transactions\n")
    
    print("5. **Time-Based Expiration**:")
    print("   - Offers have configurable expiry dates")
    print("   - Expired offers are automatically invalid\n")
    
    print("6. **Escrow Security**:")
    print("   - Funds are locked in escrow until sale completion")
    print("   - Automatic refund capability if sales fail")
    print("   - Both buyer and seller are protected\n")

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
    print("   - Asset ownership remains with buyer (for now)\n")
    
    print("4. **Sale Acceptance** (SELL transaction)")
    print("   - Seller accepts the buy offer")
    print("   - Two atomic transfers happen simultaneously:")
    print("     * Asset ownership transfers from seller to buyer")
    print("     * Payment transfers from escrow to seller")
    print("   - Advertisement status: LOCKED → CLOSED\n")
    
    print("5. **Optional: Return Process**")
    print("   - If buyer wants to return asset (REQUEST_RETURN)")
    print("   - Seller can accept return (ACCEPT_RETURN)")
    print("   - Asset returns to seller, payment returns to buyer\n")

if __name__ == "__main__":
    # Create the buy offer example
    buy_offer_tx = create_buy_offer_with_direct_escrow_example()
    
    # Demonstrate business rules
    demonstrate_business_rules()
    
    # Show transaction flow
    show_transaction_flow()
    
    print("\n=== Summary ===")
    print("The BUY_OFFER transaction now includes direct escrow transfer,")
    print("making the process more atomic and user-friendly.")
    print("- No separate escrow transaction needed")
    print("- Buyer's payment is immediately locked in escrow")
    print("- Secure, atomic completion of sales")
    print("- Automatic refund capability if needed")
