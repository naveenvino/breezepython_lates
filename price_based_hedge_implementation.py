#!/usr/bin/env python3
"""
PRICE-BASED HEDGE SELECTION
Find the hedge strike whose premium matches the percentage of main strike premium
"""

async def find_price_based_hedge_strike(
    main_strike: int,
    option_type: str,
    hedge_percentage: float,
    kite_client
) -> dict:
    """
    Find the best hedge strike based on price percentage
    
    Args:
        main_strike: The main option strike (e.g., 24500)
        option_type: PE or CE
        hedge_percentage: Percentage of main premium for hedge (e.g., 0.3 for 30%)
        kite_client: Broker client for fetching prices
    
    Returns:
        Best hedge strike and its details
    """
    
    # Step 1: Get current price of main strike
    main_symbol = f"NIFTY24SEP{main_strike}{option_type}"
    main_quote = kite_client.quote([f"NFO:{main_symbol}"])
    main_price = main_quote[f"NFO:{main_symbol}"]["last_price"]
    
    print(f"Main Strike: {main_strike}{option_type} @ ₹{main_price}")
    
    # Step 2: Calculate target hedge price
    target_hedge_price = main_price * hedge_percentage
    print(f"Target Hedge Price ({hedge_percentage*100}%): ₹{target_hedge_price:.2f}")
    
    # Step 3: Search for best matching strike
    # For PE: Search lower strikes (OTM puts for hedge)
    # For CE: Search higher strikes (OTM calls for hedge)
    
    search_range = 10  # Check 10 strikes
    strike_gap = 50 if main_strike < 25000 else 100  # NIFTY has 50/100 point gaps
    
    best_hedge_strike = None
    best_price_diff = float('inf')
    best_hedge_price = None
    
    if option_type == "PE":
        # For PUT hedge, search LOWER strikes (further OTM)
        strikes_to_check = [main_strike - (i * strike_gap) for i in range(1, search_range)]
    else:
        # For CALL hedge, search HIGHER strikes (further OTM)
        strikes_to_check = [main_strike + (i * strike_gap) for i in range(1, search_range)]
    
    print(f"\nSearching strikes: {strikes_to_check[:5]}...")
    
    # Step 4: Find the strike with price closest to target
    for strike in strikes_to_check:
        try:
            symbol = f"NIFTY24SEP{strike}{option_type}"
            quote = kite_client.quote([f"NFO:{symbol}"])
            strike_price = quote[f"NFO:{symbol}"]["last_price"]
            
            price_diff = abs(strike_price - target_hedge_price)
            
            print(f"  {strike}{option_type}: ₹{strike_price:.2f} (diff: {price_diff:.2f})")
            
            if price_diff < best_price_diff:
                best_price_diff = price_diff
                best_hedge_strike = strike
                best_hedge_price = strike_price
                
        except Exception as e:
            print(f"  {strike}: Error fetching price")
            continue
    
    print(f"\n✅ Best Hedge Strike: {best_hedge_strike}{option_type} @ ₹{best_hedge_price:.2f}")
    print(f"   Target was ₹{target_hedge_price:.2f}, difference: ₹{best_price_diff:.2f}")
    
    return {
        "hedge_strike": best_hedge_strike,
        "hedge_price": best_hedge_price,
        "main_price": main_price,
        "target_price": target_hedge_price,
        "price_match_accuracy": (1 - best_price_diff/target_hedge_price) * 100
    }


async def execute_trade_with_price_based_hedge(request):
    """
    Execute trade with price-based hedge selection
    """
    
    # Configuration
    HEDGE_PERCENTAGE = 0.30  # 30% of main premium
    
    print("=" * 60)
    print("PRICE-BASED HEDGE EXECUTION")
    print("=" * 60)
    
    # Step 1: Find the best hedge strike based on price
    hedge_data = await find_price_based_hedge_strike(
        main_strike=request.strike,
        option_type=request.option_type,
        hedge_percentage=HEDGE_PERCENTAGE,
        kite_client=kite_client
    )
    
    # Step 2: Calculate quantities (same for both legs in this strategy)
    main_quantity = request.quantity * 75  # Convert lots to contracts
    hedge_quantity = main_quantity  # Same quantity for both legs
    
    print(f"\nOrder Details:")
    print(f"Main: SELL {main_quantity} qty of {request.strike}{request.option_type} @ ₹{hedge_data['main_price']}")
    print(f"Hedge: BUY {hedge_quantity} qty of {hedge_data['hedge_strike']}{request.option_type} @ ₹{hedge_data['hedge_price']}")
    
    # Step 3: Calculate net credit/risk
    total_collected = main_quantity * hedge_data['main_price']
    total_paid = hedge_quantity * hedge_data['hedge_price'] 
    net_credit = total_collected - total_paid
    max_loss = (request.strike - hedge_data['hedge_strike']) * main_quantity
    
    print(f"\nRisk Analysis:")
    print(f"Premium Collected: ₹{total_collected:,.0f}")
    print(f"Premium Paid: ₹{total_paid:,.0f}")
    print(f"Net Credit: ₹{net_credit:,.0f}")
    print(f"Max Loss: ₹{max_loss:,.0f}")
    print(f"Risk-Reward Ratio: 1:{net_credit/max_loss:.2f}")
    
    # Step 4: Execute orders IN CORRECT ORDER
    try:
        # FIRST: BUY the hedge (protection first!)
        hedge_order = {
            "tradingsymbol": f"NIFTY24SEP{hedge_data['hedge_strike']}{request.option_type}",
            "exchange": "NFO",
            "transaction_type": "BUY",
            "quantity": hedge_quantity,
            "order_type": "MARKET",
            "product": "MIS",
            "variety": "regular"
        }
        
        print(f"\n[1/2] Placing HEDGE order (BUY)...")
        hedge_order_id = kite_client.place_order(**hedge_order)
        
        # Wait for hedge to fill
        import time
        time.sleep(0.5)
        
        # SECOND: SELL the main position
        main_order = {
            "tradingsymbol": f"NIFTY24SEP{request.strike}{request.option_type}",
            "exchange": "NFO",
            "transaction_type": "SELL",
            "quantity": main_quantity,
            "order_type": "LIMIT",
            "price": hedge_data['main_price'],
            "product": "MIS",
            "variety": "regular"
        }
        
        print(f"[2/2] Placing MAIN order (SELL)...")
        main_order_id = kite_client.place_order(**main_order)
        
        return {
            "status": "success",
            "main_strike": request.strike,
            "hedge_strike": hedge_data['hedge_strike'],
            "main_price": hedge_data['main_price'],
            "hedge_price": hedge_data['hedge_price'],
            "price_match_accuracy": f"{hedge_data['price_match_accuracy']:.1f}%",
            "net_credit": net_credit,
            "max_loss": max_loss,
            "orders": {
                "main_order_id": main_order_id,
                "hedge_order_id": hedge_order_id
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


# EXAMPLES OF PRICE-BASED HEDGE SELECTION

def demonstrate_price_based_hedge():
    """
    Show how price-based hedge selection works
    """
    
    print("\n" + "=" * 60)
    print("PRICE-BASED HEDGE EXAMPLES")
    print("=" * 60)
    
    # Example 1: 30% hedge
    print("\nExample 1: 30% Hedge")
    print("-" * 40)
    print("Main: 24500PE @ ₹100")
    print("Target hedge price: ₹30 (30% of ₹100)")
    print("Checking strikes:")
    print("  24300PE: ₹40 ❌ (too expensive)")
    print("  24200PE: ₹32 ✅ (close!)")
    print("  24100PE: ₹28 ✅ (also close!)")
    print("  24000PE: ₹22 ❌ (too cheap)")
    print("Best match: 24100PE @ ₹28")
    
    # Example 2: 50% hedge
    print("\nExample 2: 50% Hedge")
    print("-" * 40)
    print("Main: 24500CE @ ₹120")
    print("Target hedge price: ₹60 (50% of ₹120)")
    print("Checking strikes:")
    print("  24600CE: ₹85 ❌ (too expensive)")
    print("  24700CE: ₹62 ✅ (very close!)")
    print("  24800CE: ₹45 ❌ (too cheap)")
    print("Best match: 24700CE @ ₹62")
    
    # Example 3: Dynamic percentage
    print("\nExample 3: Market Condition Based")
    print("-" * 40)
    print("High volatility (VIX > 20): Use 40% hedge")
    print("Normal market (VIX 15-20): Use 30% hedge")
    print("Low volatility (VIX < 15): Use 20% hedge")


if __name__ == "__main__":
    demonstrate_price_based_hedge()
    
    print("\n" + "=" * 60)
    print("KEY POINTS:")
    print("=" * 60)
    print("1. Hedge strike is chosen by PRICE, not fixed offset")
    print("2. Finds strike with premium = X% of main premium")
    print("3. Same quantity for both legs")
    print("4. Creates a credit spread with defined risk")
    print("5. ALWAYS buy hedge first for safety!")
    print("=" * 60)