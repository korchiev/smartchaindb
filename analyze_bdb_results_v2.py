#!/usr/bin/env python3
"""Analyze BigchainDB performance results"""

with open('bdb_perf_final.csv', 'r', encoding='utf-8', errors='ignore') as f:
    lines = [l.strip() for l in f.readlines() if l.strip()]

# Parse transactions
transactions = []
for line in lines:
    if line.startswith('SUMMARY'):
        parts = line.split(',')
        print(f"\nSummary found: {parts[1]} transactions, {parts[2]} ms total")
        continue
    
    parts = line.split(',')
    if len(parts) >= 4:  # TYPE,ID,LAT,SUBMIT,MINE
        txn_type = parts[0].strip()
        # Skip if first field is not a valid transaction type
        if txn_type in ['CREATE', 'ADVERTISEMENT', 'BUY_OFFER', 'SELL', 'REQUEST_RETURN', 'SELLER_ACCEPT_RETURN', 'ACCEPT_RETURN']:
            try:
                lat_ms = float(parts[2].strip())
                submit_ms = float(parts[3].strip()) if len(parts) > 3 and parts[3].strip() else 0
                mine_ms = float(parts[4].strip()) if len(parts) > 4 and parts[4].strip() else 0
                transactions.append((txn_type, lat_ms, submit_ms, mine_ms))
            except (ValueError, IndexError) as e:
                pass

# Calculate averages per type
type_latencies = {}
for txn_type, lat_ms, submit_ms, mine_ms in transactions:
    if txn_type not in type_latencies:
        type_latencies[txn_type] = []
    type_latencies[txn_type].append((lat_ms, submit_ms, mine_ms))

print("\n" + "="*70)
print("BIGCHAINDB SHACL PERFORMANCE - AVERAGE LATENCY PER TRANSACTION TYPE")
print("="*70)
print(f"\nTotal Transactions: {len(transactions)}")
print("\nAverage Latency by Type:")
print("-"*70)
print(f"{'Transaction Type':<25} {'Count':<10} {'Avg LAT (ms)':<15} {'Avg SUBMIT (ms)':<15} {'Avg MINE (ms)':<15}")
print("-"*70)

for txn_type in sorted(type_latencies.keys()):
    lats = type_latencies[txn_type]
    avg_lat = sum(l[0] for l in lats) / len(lats)
    avg_submit = sum(l[1] for l in lats) / len(lats)
    avg_mine = sum(l[2] for l in lats) / len(lats)
    print(f"{txn_type:<25} {len(lats):<10} {avg_lat:<15.2f} {avg_submit:<15.2f} {avg_mine:<15.2f}")

print("-"*70)

# Calculate throughput
if transactions and len(transactions) > 0:
    total_lat = sum(lat for _, lat, _, _ in transactions if isinstance(lat, (int, float)))
    if total_lat > 0:
        print(f"\nTotal Test Duration: {total_lat:.2f} ms ({total_lat/1000:.2f} seconds)")
        print(f"Throughput: {len(transactions)/(total_lat/1000):.2f} TPS")
    else:
        print(f"\nTotal Transactions: {len(transactions)} (timing data available)")
    print("\nNote: MINE_MS (~1000ms) represents Tendermint consensus + SHACL validation.")
    print("      SUBMIT_MS (~1-2ms) represents HTTP post time.")
else:
    print("\nNo transactions found in log file!")
    
print("="*70)

