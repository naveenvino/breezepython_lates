"""
Script to comment out duplicate API endpoints
"""

# List of duplicate endpoints to remove (keep first occurrence, remove later ones)
duplicates_to_remove = [
    (1560, 1574),   # GET / 
    (9812, 9821),   # GET /health
    (7197, 7211),   # GET /live/positions
    (10435, 10475),  # GET /positions
    (9982, 10015),  # GET /settings/{key}
    (10017, 10054),  # PUT /settings/{key}
    (10056, 10083),  # DELETE /settings/{key}
    (10085, 10120),  # POST /save-trade-config
    (10121, 10163),  # GET /trade-config
    (10164, 10199),  # POST /save-signal-states
    (10200, 10236),  # GET /signal-states
    (10237, 10272),  # POST /save-weekday-expiry-config
    (10273, 10309),  # GET /weekday-expiry-config
    (10310, 10346),  # POST /save-exit-timing-config
]

with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Comment out the duplicate sections
for start, end in duplicates_to_remove:
    for i in range(start-1, min(end, len(lines))):
        if i < len(lines) and lines[i].strip():
            lines[i] = '# DUPLICATE: ' + lines[i]

# Write back
with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Commented out {len(duplicates_to_remove)} duplicate endpoint sections")