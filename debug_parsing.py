#!/usr/bin/env python3
"""
Debug Transaction Type Parsing

Check what's happening with the transaction type parsing in the test results.
"""

import sys
import os
sys.path.append('/usr/src/app')

# Simulate the parsing logic
test_names = [
    "chain_0_CREATE",
    "chain_0_ADVERTISEMENT", 
    "chain_0_BUY_OFFER",
    "chain_1_CREATE",
    "chain_1_ADVERTISEMENT",
    "chain_1_BUY_OFFER"
]

print("Debug Transaction Type Parsing")
print("=" * 40)

for test_name in test_names:
    tx_type = test_name.split('_')[-1]
    print(f"test_name: {test_name:<25} -> tx_type: {tx_type}")

print("\nExpected Results:")
print("CREATE -> CREATE")
print("ADVERTISEMENT -> ADVERTISEMENT") 
print("BUY_OFFER -> BUY_OFFER")

print("\nIf we see 'OFFER' instead of 'BUY_OFFER', there's a parsing issue!")

