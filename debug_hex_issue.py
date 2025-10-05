#!/usr/bin/env python3
"""
Debug script to reproduce the hexadecimal decoding issue
"""

import codecs

def test_hex_decode():
    """Test the hexadecimal decoding issue"""
    
    # Transaction ID from the logs
    tx_id = "e39e19e07193f0bd373c21bdac81e886264f07b96b62e6ed1661985583f33541"
    
    print(f"Testing transaction ID: {tx_id}")
    print(f"Length: {len(tx_id)}")
    print(f"All hex characters: {all(c in '0123456789abcdef' for c in tx_id.lower())}")
    
    try:
        # This is what's failing in memoize.py
        decoded = codecs.decode(tx_id, 'hex')
        print(f"SUCCESS: Successfully decoded: {decoded}")
        print(f"Decoded length: {len(decoded)}")
    except Exception as e:
        print(f"ERROR: Failed to decode: {e}")
    
    # Test with different variations
    test_ids = [
        tx_id,
        tx_id.upper(),
        tx_id.lower(),
        tx_id.strip(),
    ]
    
    for test_id in test_ids:
        try:
            decoded = codecs.decode(test_id, 'hex')
            print(f"SUCCESS: {test_id[:20]}... decoded successfully")
        except Exception as e:
            print(f"ERROR: {test_id[:20]}... failed: {e}")

if __name__ == "__main__":
    test_hex_decode()
