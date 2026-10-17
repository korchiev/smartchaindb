#!/usr/bin/env python3
"""Analyze BigchainDB performance results"""

with open('bdb_perf_complete.log', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Parse transactions
transactions = []
for line in lines:
    line = line.strip()
    if not line or line.startswith('TYPE,ID,LAT_MS') or 'SUMMARY' in line or 'Sequential Performance' in line or 'runs sequential' in line or 'passing' in line:
        continue
    
    if ',' in line and not line.startswith('TYPE'):
        parts = line.split(',')
        if len(parts) >= 3:
            txn_type = parts[0].strip()
            try:
                lat_ms = float(parts[2].strip())
                submit_ms = float(parts[3].strip()) if len(parts) > 3 else 0
                mine_ms = float(parts[4].strip()) if len(parts) > 4 else 0
                transactions.append((txn_type, lat_ms, submit_ms, mine_ms))
            except (ValueError, IndexError):
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
if transactions:
    total_lat = sum(l[0] for l in transactions)
    print(f"\nTotal Test Duration: {total_lat:.2f} ms ({total_lat/1000:.2f} seconds)")
    print(f"Throughput: {len(transactions)/(total_lat/1000):.2f} TPS")
    print("\nNote: MINE_MS (~1000ms) represents Tendermint consensus + SHACL validation.")
    print("      SUBMIT_MS (~1-2ms) represents HTTP post time.")
else:
    print("\nNo transactions found in log file!")
    
print("="*70)


