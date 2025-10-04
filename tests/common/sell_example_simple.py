#!/usr/bin/env python3
"""
Simple SELL transaction example using BigchainDB Transaction helper methods.
This demonstrates the complete marketplace flow from CREATE to SELL.
"""

from bigchaindb.common.crypto import generate_key_pair
from bigchaindb.models import Transaction
from bigchaindb.lib import BigchainDB
from datetime import datetime
import time

def main():
    print("=" * 70)
    print("SELL Transaction Example - Complete Marketplace Flow")
    print("=" * 70)
    
    # Initialize BigchainDB connection
    b = BigchainDB()
    
    # Generate keypairs for different actors
    seller_keypair = generate_key_pair()
    buyer_keypair = generate_key_pair()
    escrow_keypair = generate_key_pair()
    
    print(f"\n[1] Generated keypairs:")
    print(f"    Seller:  {seller_keypair.public_key}")
    print(f"    Buyer:   {buyer_keypair.public_key}")
    print(f"    Escrow:  {escrow_keypair.public_key}")
    
    # ===== STEP 1: CREATE TRANSACTION =====
    print(f"\n[2] Creating asset (CREATE transaction)...")
    
    asset_data = {
        'machineIdentifier': 'marketplace-asset-001',
        'capability': ['display', 'transfer', 'sell']
    }
    
    create_tx = Transaction.create(
        tx_signers=[seller_keypair.public_key],
        recipients=[([seller_keypair.public_key], 1)],
        asset=asset_data,
        metadata={'timestamp': datetime.utcnow().isoformat()}
    )
    create_tx_signed = create_tx.sign([seller_keypair.private_key])
    
    # Store transaction
    b.store_bulk_transactions([create_tx_signed])
    asset_id = create_tx_signed.id
    print(f"    ✅ CREATE: {asset_id}")
    
    time.sleep(1)
    
    # ===== STEP 2: ADVERTISEMENT TRANSACTION =====
    print(f"\n[3] Creating advertisement (ADVERTISEMENT transaction)...")
    
    # Build advertisement using create() then modify operation
    ad_tx = Transaction.create(
        tx_signers=[seller_keypair.public_key],
        recipients=[([seller_keypair.public_key], 1)],
        asset=None,  # Will set manually
        metadata={
            'status': 'OPEN',
            'advertiser_public_key': seller_keypair.public_key,
            'price': '1000.00',
            'description': 'Marketplace asset for sale',
            'category': 'Digital Goods',
            'requestCreationTimestamp': datetime.utcnow().isoformat()
        }
    )
    # Manually set operation and asset
    ad_tx.operation = 'ADVERTISEMENT'
    ad_tx.asset = {'id': asset_id}
    ad_tx_signed = ad_tx.sign([seller_keypair.private_key])
    
    b.store_bulk_transactions([ad_tx_signed])
    ad_id = ad_tx_signed.id
    print(f"    ✅ ADVERTISEMENT: {ad_id}")
    
    time.sleep(1)
    
    # ===== STEP 3: BUY_OFFER TRANSACTION =====
    print(f"\n[4] Creating buy offer (BUY_OFFER transaction)...")
    
    # Prepare input for BUY_OFFER (buyer's funds)
    # For simplicity, create a payment asset for the buyer
    buyer_payment_tx = Transaction.create(
        tx_signers=[buyer_keypair.public_key],
        recipients=[([buyer_keypair.public_key], 900)],
        asset={'machineIdentifier': 'buyer-funds', 'capability': ['payment']},
        metadata={'purpose': 'payment_for_asset'}
    )
    buyer_payment_signed = buyer_payment_tx.sign([buyer_keypair.private_key])
    b.store_bulk_transactions([buyer_payment_signed])
    
    time.sleep(1)
    
    # Now create the BUY_OFFER using the buyer's funds as input
    buy_offer_input = buyer_payment_signed.to_inputs()[0]
    
    buy_offer_tx = Transaction.buy_offer(
        inputs=[buy_offer_input],
        asset_id=asset_id,
        advertisement_id=ad_id,
        metadata={
            'buyer_public_key': buyer_keypair.public_key,
            'offer_amount': 900,  # Number for validation
            'offer_currency': 'USD',
            'offer_timestamp': datetime.utcnow().isoformat() + 'Z',
            'offer_expiry': datetime.utcnow().replace(day=datetime.utcnow().day + 7).isoformat() + 'Z',
            'escrow_public_key': escrow_keypair.public_key,
            'requestCreationTimestamp': datetime.utcnow().isoformat()
        }
    )
    buy_offer_signed = buy_offer_tx.sign([buyer_keypair.private_key])
    
    b.store_bulk_transactions([buy_offer_signed])
    buy_offer_id = buy_offer_signed.id
    print(f"    ✅ BUY_OFFER: {buy_offer_id}")
    
    time.sleep(1)
    
    # ===== STEP 4: SELL TRANSACTION =====
    print(f"\n[5] Executing sale (SELL transaction)...")
    
    # Prepare input for SELL (the asset)
    sell_input = create_tx_signed.to_inputs()[0]
    
    sell_tx = Transaction.sell(
        inputs=[sell_input],
        asset_id=asset_id,
        buy_offer_id=buy_offer_id,
        metadata={
            'seller_public_key': seller_keypair.public_key,
            'buyer_public_key': buyer_keypair.public_key,
            'sale_amount': 900,  # Number for validation
            'sale_currency': 'USD',
            'sale_timestamp': datetime.utcnow().isoformat(),
            'requestCreationTimestamp': datetime.utcnow().isoformat()
        }
    )
    sell_signed = sell_tx.sign([seller_keypair.private_key])
    
    b.store_bulk_transactions([sell_signed])
    sell_id = sell_signed.id
    print(f"    ✅ SELL: {sell_id}")
    
    # ===== VERIFICATION =====
    print(f"\n[6] Transaction Chain:")
    print(f"    CREATE       → {asset_id}")
    print(f"    ADVERTISEMENT → {ad_id}")
    print(f"    BUY_OFFER    → {buy_offer_id}")
    print(f"    SELL         → {sell_id}")
    
    print(f"\n[7] SELL Transaction Details:")
    print(f"    Inputs:  1 (asset from CREATE)")
    print(f"    Outputs: 2 (asset to buyer, payment to seller)")
    print(f"    Asset Transfer:   {asset_id[:20]}... → {buyer_keypair.public_key[:20]}...")
    print(f"    Payment Transfer: 900 USD → {seller_keypair.public_key[:20]}...")
    
    print(f"\n{'=' * 70}")
    print("✅ Complete marketplace flow executed successfully!")
    print(f"{'=' * 70}")
    
    return {
        'asset_id': asset_id,
        'advertisement_id': ad_id,
        'buy_offer_id': buy_offer_id,
        'sell_id': sell_id
    }

if __name__ == '__main__':
    try:
        result = main()
        print(f"\n✅ All transactions committed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

