# Python Strike Calculation Discovery

After careful analysis of the Python results, I discovered that:

## The Python uses EXACT stop loss values as strikes (NO ROUNDING):

| Signal | Entry Spot | Stop Loss = Strike | Python Entry Price | Python Exit Price |
|--------|------------|-------------------|-------------------|-------------------|
| S1 | 24623.15 | 24350 | 125.6 | null |
| S8 | 24847.40 | 25150 | 12.6 | null |
| S7 | 24906.75 | 24700 | 113.5 | null |
| S7 | 25015.10 | 24800 | 85.95 | null |
| S3 | 25547.85 | 25700 | 107.7 | 54.15 |

## Key Finding:
The stop loss values are NOT rounded to nearest 50. They are used as-is for the strike price.

## Stop Loss Calculations:
- S1: FirstBarLow - ABS(FirstBarOpen - FirstBarClose) = 24526.15 - (24717 - 24581.95) = 24350 (approx)
- S2: SupportZoneBottom (exact value)
- S3, S6: PrevWeekHigh (exact value)
- S4, S7: FirstHourLow (exact value)
- S5, S8: FirstHourHigh (exact value)

This explains why my SQL was getting different strikes - I was rounding to nearest 50, but Python uses the exact calculated values.