#!/usr/bin/env python3
"""
CRITICAL FIX: Hedge Execution Order and Percentage-Based Hedging
This fixes the dangerous bug where SELL executes before BUY hedge
"""

def execute_signal_with_proper_hedge(request):
    """
    CORRECT ORDER:
    ENTRY: 1) BUY hedge first, 2) SELL main
    EXIT:  1) BUY main first, 2) SELL hedge
    """
    
    # Calculate hedge percentage (configurable)
    HEDGE_PERCENTAGE = 0.3  # 30% hedge - can be made configurable
    
    # Calculate quantities
    main_quantity = request.quantity * 75  # Convert lots to contracts
    hedge_quantity = int(main_quantity * HEDGE_PERCENTAGE)  # Percentage-based
    
    # Calculate hedge strike
    if request.option_type == "PE":
        hedge_strike = request.strike - 200  # Lower strike for PUT hedge
    else:
        hedge_strike = request.strike + 200  # Higher strike for CALL hedge
    
    # Prepare symbols
    main_symbol = f"NIFTY{request.expiry}{request.strike}{request.option_type}"
    hedge_symbol = f"NIFTY{request.expiry}{hedge_strike}{request.option_type}"
    
    try:
        if request.action == "ENTRY":
            # ==========================================
            # ENTRY: BUY HEDGE FIRST (PROTECT FIRST!)
            # ==========================================
            
            # Step 1: BUY HEDGE FIRST - THIS IS CRITICAL!
            if request.hedge_enabled:
                hedge_order = {
                    "tradingsymbol": hedge_symbol,
                    "exchange": "NFO",
                    "transaction_type": "BUY",  # BUY the hedge
                    "quantity": hedge_quantity,
                    "order_type": "MARKET",  # Market order for immediate fill
                    "product": "MIS",
                    "variety": "regular"
                }
                
                print(f"[1/2] PLACING HEDGE FIRST: BUY {hedge_quantity} of {hedge_symbol}")
                hedge_order_id = kite_client.place_order(**hedge_order)
                
                # Wait for hedge to fill (optional but recommended)
                import time
                time.sleep(0.5)  # Small delay to ensure hedge fills
            
            # Step 2: SELL MAIN POSITION (Now protected by hedge)
            main_order = {
                "tradingsymbol": main_symbol,
                "exchange": "NFO", 
                "transaction_type": "SELL",  # SELL main position
                "quantity": main_quantity,
                "order_type": "LIMIT",
                "price": request.entry_price,
                "product": "MIS",
                "variety": "regular"
            }
            
            print(f"[2/2] PLACING MAIN: SELL {main_quantity} of {main_symbol}")
            main_order_id = kite_client.place_order(**main_order)
            
            return {
                "status": "success",
                "message": "Entry executed in correct order: Hedge first, then Main",
                "hedge_order_id": hedge_order_id if request.hedge_enabled else None,
                "main_order_id": main_order_id,
                "hedge_quantity": hedge_quantity,
                "main_quantity": main_quantity,
                "hedge_percentage": f"{HEDGE_PERCENTAGE*100}%"
            }
            
        elif request.action == "EXIT":
            # ==========================================
            # EXIT: CLOSE MAIN FIRST, THEN HEDGE
            # ==========================================
            
            # Step 1: BUY BACK MAIN POSITION FIRST
            main_exit_order = {
                "tradingsymbol": main_symbol,
                "exchange": "NFO",
                "transaction_type": "BUY",  # BUY to close short
                "quantity": main_quantity,
                "order_type": "MARKET",  # Market order for immediate exit
                "product": "MIS",
                "variety": "regular"
            }
            
            print(f"[1/2] CLOSING MAIN FIRST: BUY {main_quantity} of {main_symbol}")
            main_exit_id = kite_client.place_order(**main_exit_order)
            
            # Wait for main to close
            import time
            time.sleep(0.5)
            
            # Step 2: SELL HEDGE LAST
            if request.hedge_enabled:
                hedge_exit_order = {
                    "tradingsymbol": hedge_symbol,
                    "exchange": "NFO",
                    "transaction_type": "SELL",  # SELL to close long hedge
                    "quantity": hedge_quantity,
                    "order_type": "MARKET",
                    "product": "MIS",
                    "variety": "regular"
                }
                
                print(f"[2/2] CLOSING HEDGE: SELL {hedge_quantity} of {hedge_symbol}")
                hedge_exit_id = kite_client.place_order(**hedge_exit_order)
            
            return {
                "status": "success",
                "message": "Exit executed in correct order: Main first, then Hedge",
                "main_exit_id": main_exit_id,
                "hedge_exit_id": hedge_exit_id if request.hedge_enabled else None
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Order execution failed: {str(e)}",
            "critical": "Check your positions manually!"
        }


# CONFIGURATION FOR PERCENTAGE-BASED HEDGING
HEDGE_CONFIG = {
    "enabled": True,
    "percentage": 0.3,  # 30% hedge (can be 0.2 for 20%, 0.5 for 50%, etc.)
    "offset": 200,      # Strike offset in points
    "order_type": "MARKET",  # Always use MARKET for hedge to ensure fill
}

def calculate_hedge_quantity(main_quantity, hedge_percentage):
    """
    Calculate hedge quantity based on percentage
    
    Examples:
    - 10 lots (750 contracts) with 30% hedge = 225 contracts (3 lots)
    - 10 lots (750 contracts) with 50% hedge = 375 contracts (5 lots)
    - 10 lots (750 contracts) with 100% hedge = 750 contracts (10 lots)
    """
    return int(main_quantity * hedge_percentage)


# RISK COMPARISON WITH PERCENTAGE-BASED HEDGING

def calculate_risk_with_percentage_hedge(main_lots, hedge_percentage):
    """
    Calculate max risk with different hedge percentages
    """
    main_qty = main_lots * 75
    hedge_qty = int(main_qty * hedge_percentage)
    
    # Assume 200 point spread
    max_loss_main = main_qty * 200  # If option moves 200 points against
    max_gain_hedge = hedge_qty * 200  # Hedge gains 200 points
    
    net_max_loss = max_loss_main - max_gain_hedge
    
    print(f"\nRisk Analysis for {main_lots} lots with {hedge_percentage*100}% hedge:")
    print(f"Main Position: {main_qty} contracts")
    print(f"Hedge Position: {hedge_qty} contracts ({hedge_qty/75:.1f} lots)")
    print(f"Max Loss without hedge: ₹{max_loss_main:,}")
    print(f"Hedge protection: ₹{max_gain_hedge:,}")
    print(f"Net Max Loss: ₹{net_max_loss:,}")
    print(f"Risk Reduction: {(max_gain_hedge/max_loss_main)*100:.1f}%")
    
    return net_max_loss


# Examples with different hedge percentages
if __name__ == "__main__":
    print("=" * 60)
    print("HEDGE EXECUTION ORDER FIX")
    print("=" * 60)
    
    print("\nCRITICAL CHANGES:")
    print("1. ENTRY: BUY hedge FIRST, then SELL main")
    print("2. EXIT: BUY main FIRST, then SELL hedge")
    print("3. Percentage-based hedging (configurable)")
    
    # Show risk with different hedge percentages
    for percentage in [0.2, 0.3, 0.5, 0.75, 1.0]:
        calculate_risk_with_percentage_hedge(10, percentage)
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    print("- 30% hedge: Good balance of protection vs cost")
    print("- 50% hedge: Strong protection, moderate cost")
    print("- 100% hedge: Maximum protection (full spread)")
    print("=" * 60)