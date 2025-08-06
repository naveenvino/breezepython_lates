# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# BreezeConnect Trading System - Project Guidelines

## Project Overview
This is a trading system using Breeze API for Indian markets (NIFTY options trading) with backtesting capabilities.

## Critical Rules - DO NOT VIOLATE
1. **NEVER change working code without explicit permission**
2. **NEVER modify default parameters in APIs**
3. **NEVER add "improvements" unless specifically requested**
4. **NEVER change response formats of working endpoints**
5. **ALWAYS test with the exact same parameters that were working before**

## Code Style Guidelines
- **NO unnecessary comments** - The code should be self-documenting
- **NO commented-out code** - Remove it completely
- **NO emoji in code** unless explicitly requested
- **MINIMAL output** - Be concise and direct in responses

## Common Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Breeze API credentials
```

### Running APIs
```bash
# Start unified API (recommended - port 8000)
python unified_api_correct.py

# Alternative: Main clean architecture API
python -m src.api.main

# Alternative: Data collection API (port 8002)
python -m api.data_collection_api

# Alternative: Backtest APIs
python -m api.backtest_api_post  # POST endpoint
python -m api.backtest_api_get   # GET endpoint
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Quick test of unified API
run_and_test_api.bat

# Test backtest for July 2025
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{"from_date": "2025-07-14", "to_date": "2025-07-18", "signals_to_test": ["S1"]}'
```

### Linting and Type Checking
```bash
# Currently no specific linter configured
# If adding: use ruff or flake8, mypy for type checking
```

## High-Level Architecture

The system follows clean architecture principles with clear separation of concerns:

```
src/
├── domain/              # Core business logic (entities, value objects, domain services)
│   ├── entities/        # Trade, Option, MarketData models
│   ├── repositories/    # Interface definitions for data access
│   ├── services/        # Signal evaluation, risk management, pricing
│   └── value_objects/   # SignalTypes, StrikePrice, TradingSymbol
│
├── application/         # Use cases and orchestration
│   ├── use_cases/       # RunBacktestUseCase, CollectWeeklyDataUseCase
│   ├── dto/             # Request/Response models for API
│   └── interfaces/      # Application service interfaces
│
├── infrastructure/      # External integrations
│   ├── brokers/breeze/  # Breeze API integration
│   ├── database/        # SQL Server with models and repositories
│   ├── services/        # Implementation of domain/app interfaces
│   └── cache/           # Smart caching for performance
│
└── api/                 # FastAPI routes
    └── routers/         # Organized by feature (backtest, data, signals)

unified_api_correct.py   # Combined API with all features (port 8000) - ROOT DIRECTORY
api/                     # Standalone API modules (outside clean architecture)
├── data_collection_api.py    # NIFTY & options data collection (if exists)
├── backtest_api_*.py         # Individual backtest endpoints (if exists)
└── optimizations/            # Performance enhancement modules
```

### Key Design Patterns
- **Repository Pattern**: Abstract data access behind interfaces
- **Use Case Pattern**: Each business operation as a separate class
- **Dependency Injection**: Loose coupling via DI container
- **Domain Events**: Signal detection triggers downstream processes
- **Value Objects**: Immutable domain concepts (SignalTypes, StrikePrice)

## Database Context
- **SQL Server** with connection: `(localdb)\mssqllocaldb`
- **Main Tables**:
  - `BacktestRuns`: Backtest execution metadata
  - `BacktestTrades`: Individual trade records
  - `BacktestPositions`: Position details (main/hedge)
  - `NIFTYData_5Min`: 5-minute candle data
  - `NIFTYData_Hourly`: Aggregated hourly data
  - `OptionsData`: Historical options prices with Greeks
- **Data Storage**: 5-minute intervals, hourly aggregations
- **Options**: Weekly expiry on Thursday

## Trading System Context

### Signals (S1-S8)
- **S1**: Bear Trap (Bullish) - Sell PUT
- **S2**: Support Hold (Bullish) - Sell PUT
- **S3**: Resistance Hold (Bearish) - Sell CALL
- **S4**: Bias Failure Bull (Bullish) - Sell PUT
- **S5**: Bias Failure Bear (Bearish) - Sell CALL
- **S6**: Weakness Confirmed (Bearish) - Sell CALL
- **S7**: Breakout Confirmed (Bullish) - Sell PUT
- **S8**: Breakdown Confirmed (Bearish) - Sell CALL

### Trading Rules
- **Entry**: Second candle after signal (typically 11:15 AM)
- **Stop Loss**: Main strike price (e.g., 25000)
- **Position Sizing**: Default 10 lots × 75 quantity = 750 total
- **Hedging**: Optional, default 200 points offset
- **Commission**: Rs. 40 per lot
- **Initial Capital**: Rs. 500,000

### Known Working Test Case
- **Period**: July 14-18, 2025
- **Signal**: S1
- **Expected**: 1 trade with specific entry/exit behavior

## Working API Patterns
When asked to modify or consolidate APIs:
1. Copy the working code EXACTLY
2. Change ONLY what is explicitly requested (e.g., port number)
3. Keep all defaults, parameters, and behavior identical
4. Test with the same test case that was working

## DO NOT Touch List
1. Stop loss calculation logic (uses main strike as stop loss)
2. Entry time calculation (second candle after signal)
3. Working database queries
4. Signal evaluation logic
5. Option pricing service

## When Creating/Modifying APIs
1. Start with the simplest working version
2. Do not add features unless requested
3. Keep exact same defaults as working versions
4. Use the same time handling (9:00 to 16:00 for backtests)
5. Preserve exact response formats
6. **ALWAYS scan entire source file for ALL endpoints** using: `@app.post|@app.get|@app.delete|@app.put`
7. **List all found endpoints before consolidating** to ensure nothing is missed
8. **Compare endpoint count** - if original has 10 endpoints, consolidated must have 10

## Debugging Approach
1. If something was working before, check what changed
2. Compare with working backup versions
3. Use exact same test parameters
4. Don't assume - verify with actual code
5. **ALWAYS show code when explaining behavior** - Never make claims without showing the exact code
6. **Trace through calculations with actual values** - Show step-by-step execution
7. **No assumptions** - If unsure, read the code first before responding

## Performance Optimizations
The system includes several optimization modules in `api/optimizations/`:
- **Smart Caching**: Reduces redundant API calls
- **Bulk Operations**: Batch database inserts
- **Connection Pooling**: Optimized DB connections
- **Parallel Processing**: Multi-threaded data collection
- **Async Operations**: Non-blocking I/O for better throughput

## Environment Variables
Required in `.env`:
```
# Database
DB_SERVER=(localdb)\mssqllocaldb
DB_NAME=KiteConnectApi

# Breeze API
BREEZE_API_KEY=your_api_key
BREEZE_API_SECRET=your_api_secret
BREEZE_API_SESSION=your_session_token
```

## Remember
"Just consolidate working APIs" means:
- Copy them exactly
- Put them in one file
- Change only the port
- Nothing else

## Subagent Usage Guidelines
Use subagents for:
1. **Complex searches**: "Find all signal evaluation logic" → Use general-purpose agent
2. **Testing tasks**: "Create tests for new features" → Use testing-automation agent
3. **Architecture decisions**: "Design new trading features" → Use trading-architect agent
4. **Performance optimization**: "Optimize data processing" → Use python-finance-expert agent
5. **Parallel exploration**: Use multiple agents to explore different parts simultaneously

Example prompts that trigger subagent use:
- "Use subagents to find all places where options are priced"
- "Delegate testing of the backtest API to appropriate agent"
- "Use parallel tasks to check data in all tables"