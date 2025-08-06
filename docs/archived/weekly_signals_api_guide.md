**API Implementation Guide: Weekly Levels & Signals (Revised)**

This guide provides a complete, step-by-step process for building a trading signals API based on 1-hour candle data. This revised version includes more precise conditions to ensure a 1:1 match with the source indicator's logic.

---

### Step 1: Weekly Zone Calculations

Run once at the start of each new trading week.

**Aggregate Previous Week's 1H Data:**

- `prevWeekHigh`: Highest high of all 1H candles.
- `prevWeekLow`: Lowest low of all 1H candles.
- `prevWeekClose`: Close price of the final 1H candle.

**Calculate Previous Week's 4-Hour Body Levels:**

- Group all 1H candles into sequential 4-hour blocks.
- For each block:
  - `bodyTop = max(open, close)`
  - `bodyBottom = min(open, close)`
- `prevMax4hBody`: Highest bodyTop across all 4H blocks.
- `prevMin4hBody`: Lowest bodyBottom across all 4H blocks.

**Define Zones:**

- **Resistance Zone**:
  - `upperZTop = max(prevWeekHigh, prevMax4hBody)`
  - `upperZBottom = min(prevWeekHigh, prevMax4hBody)`
- **Support Zone**:
  - `lowerZTop = max(prevWeekLow, prevMin4hBody)`
  - `lowerZBottom = min(prevWeekLow, prevMin4hBody)`

**Margins:**

- `marginHigh = max((upperZTop - upperZBottom) * 3, minTick * 5)`
- `marginLow = max((lowerZTop - lowerZBottom) * 3, minTick * 5)`

---

### Step 2: Weekly Bias Calculation

Also runs once at the start of the week.

**Distances:**

- `distToResistance = abs(prevWeekClose - prevMax4hBody)`
- `distToSupport = abs(prevWeekClose - prevMin4hBody)`

**Determine Bias (weeklySig):**

- If `distToResistance < distToSupport`: **Bearish (-1)**
- If `distToSupport < distToResistance`: **Bullish (1)**
- If equal: **Neutral (0)**

---

### Step 3: Signal & Stop Loss Calculations

Runs on the close of each new 1H candle. Use state variables to ensure only one signal per week.

**Track:** `weeklyMaxHigh`, `weeklyMinLow`, `weeklyMaxClose`, `weeklyMinClose`

#### S1: Bear Trap (Bullish)

- Conditions (2nd 1H candle):
  - `firstBar.open >= lowerZBottom`
  - `firstBar.close < lowerZBottom`
  - `currentCandle.close > firstBar.low`
- **Stop Loss:** `firstBar.low - abs(firstBar.open - firstBar.close)`

#### S2: Support Hold (Bullish)

- Conditions (2nd 1H candle):
  - `weeklySig == 1`
  - `firstBar.open > prevWeekLow`
  - Proximity checks for `lowerZBottom`
  - `firstBar.close >= lowerZBottom AND >= prevWeekClose`
  - `currentCandle.close >= firstBar.low AND > lowerZBottom AND > prevWeekClose`
- **Stop Loss:** `lowerZBottom`

#### S3: Resistance Hold (Bearish)

- Base:
  - `weeklySig == -1`
  - Proximity to `upperZBottom`
  - `firstBar.close <= prevWeekHigh`
- **Trigger A** (2nd candle):
  - `currentCandle.close < firstBar.high AND < upperZBottom`
  - `(firstBar.high >= upperZBottom OR currentCandle.high >= upperZBottom)`
- **Trigger B** (any candle):
  - `currentCandle.close < firstBar.low AND < upperZBottom`
  - `currentCandle.close < weeklyMinLow/MinClose before this candle`
- **Stop Loss:** `prevWeekHigh`

#### S4: Bias Failure (Bullish)

- Conditions:
  - `weeklySig == -1`
  - `firstBar.open > upperZTop`
  - **1H Breakout Logic** (see below)
- **1H Breakout Logic:**
  - Day 1: `currentCandle.close > firstBar.high`
  - Day 2+: `breakoutCandle.close > firstBar.high`, then another candle closes above breakoutCandle.high
- **Stop Loss:** `firstBar.low`

#### S5: Bias Failure (Bearish)

- Conditions:
  - `weeklySig == 1`
  - `firstBar.open < lowerZBottom`
  - `firstBar.close < lowerZBottom AND < prevWeekLow`
  - `currentCandle.close < firstBar.low`
- **Stop Loss:** `firstBar.high`

#### S6: Weakness Confirmed (Bearish)

- Base:
  - `weeklySig == -1`
  - `firstBar.high >= upperZBottom`
  - `firstBar.close <= upperZTop AND <= prevWeekHigh`
- **Trigger:** Same as S3
- **Stop Loss:** `prevWeekHigh`

#### S7: 1H Breakout Confirmed (Bullish)

- Conditions:
  - 1H Breakout Logic confirms
  - `currentCandle.close >= prevWeekHigh OR gap >= 0.4%`
  - `currentCandle.close > weeklyMaxHigh AND > weeklyMaxClose before this candle`
- **Stop Loss:** `firstBar.low`

#### S8: 1H Breakdown Confirmed (Bearish)

- Conditions:
  - 1H Breakdown logic confirms (mirror of S4)
  - `upperZBottom` was touched this week
  - `currentCandle.close < upperZBottom`
  - `currentCandle.close < weeklyMinLow AND < weeklyMinClose before this candle`
- **Stop Loss:** `firstBar.high`

---

### Step 4: Alert Definition

When a signal triggers, generate a JSON alert.

**Alert Structure:**

```json
{
  "strike": 46100,
  "type": "CE",
  "signal": "S5",
  "action": "Entry"
}
```

**Fields:**

- `signal`: e.g., "S1", "S5"
- `action`: Always "Entry"
- `type`: "PE" for Bullish (S1, S2, S4, S7), "CE" for Bearish (S3, S5, S6, S8)
- `strike`: Rounded stop loss (nearest 100)

---

### Step 5: P&L Dashboard Logic

Maintain a log of triggered trades.

**TradeLog Structure:**

```json
{
  weekStartDate,
  signalId,
  direction,
  stopLoss,
  entryTime,
  outcome: "OPEN",
  exitTime: null
}
```

**Manage Open Trades:**

- On each new 1H candle:
  - If Bullish and `close <= stopLoss`: outcome = "LOSS"
  - If Bearish and `close >= stopLoss`: outcome = "LOSS"
  - Record `exitTime` when trade closes

**Win Condition:**

- At new week start, open trades from previous week = "WIN"

**Dashboard Endpoints:**

- **Trade Log View**: Filter by year/month, return raw TradeLog list
- **Performance Summary View**:
  - Aggregate by `signalId`
  - Count trades, wins, losses
  - Win rate = `(wins / totalTrades) * 100`
  - Return summary + overall totals

