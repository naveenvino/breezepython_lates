"""
Iceberg Order Service for handling large orders with hedge protection
Splits large orders into smaller chunks to comply with exchange limits
Ensures hedge orders are placed before main orders for risk protection
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class IcebergOrderService:
    """
    Handles splitting large orders into smaller chunks
    For NIFTY options:
    - 1 lot = 75 quantity
    - Max quantity per order = 1800 (24 lots)
    - Freeze quantity = 1800 (exchange limit)
    """
    
    # Exchange limits for NIFTY options
    MAX_LOTS_PER_ORDER = 24  # 1800 quantity / 75 = 24 lots
    MAX_QUANTITY_PER_ORDER = 1800  # Exchange freeze quantity
    LOT_SIZE = 75
    
    def __init__(self, kite_client=None):
        self.kite_client = kite_client
        
    def calculate_order_splits(self, total_lots: int) -> List[int]:
        """
        Calculate how to split a large order into smaller chunks
        
        Args:
            total_lots: Total number of lots to order
            
        Returns:
            List of lot sizes for each order
        """
        if total_lots <= 0:
            return []
            
        if total_lots <= self.MAX_LOTS_PER_ORDER:
            # No split needed
            return [total_lots]
            
        # Split into multiple orders
        splits = []
        remaining_lots = total_lots
        
        while remaining_lots > 0:
            if remaining_lots > self.MAX_LOTS_PER_ORDER:
                splits.append(self.MAX_LOTS_PER_ORDER)
                remaining_lots -= self.MAX_LOTS_PER_ORDER
            else:
                splits.append(remaining_lots)
                remaining_lots = 0
                
        logger.info(f"Split {total_lots} lots into {len(splits)} orders: {splits}")
        return splits
    
    async def place_iceberg_order(
        self,
        tradingsymbol: str,
        transaction_type: str,  # BUY or SELL
        total_lots: int,
        order_type: str = "MARKET",
        product: str = "MIS",
        exchange: str = "NFO",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place an iceberg order by splitting into smaller chunks
        
        Args:
            tradingsymbol: Trading symbol
            transaction_type: BUY or SELL
            total_lots: Total number of lots
            order_type: MARKET or LIMIT
            product: MIS, CNC, NRML
            exchange: Exchange (NFO for options)
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            
        Returns:
            Dictionary with order results
        """
        try:
            # Validate inputs
            if total_lots <= 0 or total_lots > 100:
                raise ValueError(f"Invalid lot size: {total_lots}. Must be 1-100")
                
            # Calculate order splits
            lot_splits = self.calculate_order_splits(total_lots)
            
            # Place orders
            order_ids = []
            failed_orders = []
            total_quantity_placed = 0
            
            for i, lots in enumerate(lot_splits):
                quantity = lots * self.LOT_SIZE
                
                try:
                    logger.info(f"Placing order {i+1}/{len(lot_splits)}: {lots} lots ({quantity} qty)")
                    
                    # Build order parameters
                    order_params = {
                        "tradingsymbol": tradingsymbol,
                        "exchange": exchange,
                        "transaction_type": transaction_type,
                        "quantity": quantity,
                        "order_type": order_type,
                        "product": product,
                        "variety": "regular"
                    }
                    
                    # Add price for LIMIT orders
                    if order_type == "LIMIT" and price:
                        order_params["price"] = price
                        
                    # Add trigger price for SL orders
                    if trigger_price:
                        order_params["trigger_price"] = trigger_price
                        
                    # Place the order
                    if self.kite_client:
                        order_id = self.kite_client.kite.place_order(**order_params)
                        order_ids.append(order_id)
                        total_quantity_placed += quantity
                        
                        logger.info(f"Order placed successfully: {order_id}")
                        
                        # Small delay between orders to avoid rate limiting
                        if i < len(lot_splits) - 1:
                            await asyncio.sleep(0.5)
                    else:
                        # Mock order for testing
                        order_id = f"TEST_{tradingsymbol}_{i+1}"
                        order_ids.append(order_id)
                        total_quantity_placed += quantity
                        
                except Exception as e:
                    logger.error(f"Failed to place order {i+1}: {e}")
                    failed_orders.append({
                        "lots": lots,
                        "error": str(e)
                    })
                    
            # Prepare response
            result = {
                "status": "success" if not failed_orders else "partial",
                "total_lots_requested": total_lots,
                "total_lots_placed": total_quantity_placed // self.LOT_SIZE,
                "total_quantity_placed": total_quantity_placed,
                "orders_placed": len(order_ids),
                "order_ids": order_ids,
                "splits": lot_splits,
                "timestamp": datetime.now().isoformat()
            }
            
            if failed_orders:
                result["failed_orders"] = failed_orders
                result["message"] = f"Placed {len(order_ids)} of {len(lot_splits)} orders"
            else:
                result["message"] = f"Successfully placed all {len(order_ids)} orders"
                
            return result
            
        except Exception as e:
            logger.error(f"Error in iceberg order placement: {e}")
            return {
                "status": "error",
                "message": str(e),
                "total_lots_requested": total_lots,
                "timestamp": datetime.now().isoformat()
            }
    
    async def place_hedged_iceberg_order(
        self,
        main_symbol: str,
        hedge_symbol: str,
        total_lots: int,
        action: str = "ENTRY",  # ENTRY or EXIT
        order_type: str = "MARKET",
        product: str = "MIS",
        exchange: str = "NFO",
        main_price: Optional[float] = None,
        hedge_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place hedged iceberg orders with proper sequencing
        ENTRY: Hedge BUY first, then Main SELL
        EXIT: Main BUY first, then Hedge SELL
        
        Args:
            main_symbol: Main leg trading symbol
            hedge_symbol: Hedge leg trading symbol
            total_lots: Total number of lots
            action: ENTRY or EXIT
            order_type: MARKET or LIMIT
            product: MIS, CNC, NRML
            exchange: Exchange (NFO for options)
            main_price: Limit price for main leg
            hedge_price: Limit price for hedge leg
            
        Returns:
            Dictionary with order results
        """
        try:
            # Validate inputs
            if total_lots <= 0 or total_lots > 100:
                raise ValueError(f"Invalid lot size: {total_lots}. Must be 1-100")
            
            if action not in ["ENTRY", "EXIT"]:
                raise ValueError(f"Invalid action: {action}. Must be ENTRY or EXIT")
                
            # Calculate order splits
            lot_splits = self.calculate_order_splits(total_lots)
            logger.info(f"Hedged iceberg order: {action} {total_lots} lots split into {len(lot_splits)} chunks")
            
            # Track results
            main_order_ids = []
            hedge_order_ids = []
            failed_orders = []
            total_main_placed = 0
            total_hedge_placed = 0
            
            # Process each chunk
            for i, lots in enumerate(lot_splits):
                quantity = lots * self.LOT_SIZE
                chunk_num = i + 1
                
                try:
                    if action == "ENTRY":
                        # ENTRY: Hedge BUY first, then Main SELL
                        logger.info(f"[ENTRY] Chunk {chunk_num}/{len(lot_splits)}: {lots} lots")
                        
                        # 1. Place HEDGE BUY order first
                        hedge_params = {
                            "tradingsymbol": hedge_symbol,
                            "exchange": exchange,
                            "transaction_type": "BUY",
                            "quantity": quantity,
                            "order_type": order_type,
                            "product": product,
                            "variety": "regular"
                        }
                        if order_type == "LIMIT" and hedge_price:
                            hedge_params["price"] = hedge_price
                            
                        if self.kite_client:
                            logger.info(f"  [HEDGE] Placing BUY {hedge_symbol} - {quantity} qty")
                            hedge_id = self.kite_client.kite.place_order(**hedge_params)
                            hedge_order_ids.append(hedge_id)
                            total_hedge_placed += quantity
                            
                            # Small delay to ensure hedge fills
                            time.sleep(0.3)
                        else:
                            hedge_id = f"TEST_HEDGE_{chunk_num}"
                            hedge_order_ids.append(hedge_id)
                            total_hedge_placed += quantity
                        
                        # 2. Place MAIN SELL order (now protected)
                        main_params = {
                            "tradingsymbol": main_symbol,
                            "exchange": exchange,
                            "transaction_type": "SELL",
                            "quantity": quantity,
                            "order_type": order_type,
                            "product": product,
                            "variety": "regular"
                        }
                        if order_type == "LIMIT" and main_price:
                            main_params["price"] = main_price
                            
                        if self.kite_client:
                            logger.info(f"  [MAIN] Placing SELL {main_symbol} - {quantity} qty")
                            main_id = self.kite_client.kite.place_order(**main_params)
                            main_order_ids.append(main_id)
                            total_main_placed += quantity
                        else:
                            main_id = f"TEST_MAIN_{chunk_num}"
                            main_order_ids.append(main_id)
                            total_main_placed += quantity
                            
                    else:  # EXIT
                        # EXIT: Main BUY first, then Hedge SELL
                        logger.info(f"[EXIT] Chunk {chunk_num}/{len(lot_splits)}: {lots} lots")
                        
                        # 1. Place MAIN BUY order first (close position)
                        main_params = {
                            "tradingsymbol": main_symbol,
                            "exchange": exchange,
                            "transaction_type": "BUY",
                            "quantity": quantity,
                            "order_type": order_type,
                            "product": product,
                            "variety": "regular"
                        }
                        if order_type == "LIMIT" and main_price:
                            main_params["price"] = main_price
                            
                        if self.kite_client:
                            logger.info(f"  [MAIN] Placing BUY {main_symbol} - {quantity} qty")
                            main_id = self.kite_client.kite.place_order(**main_params)
                            main_order_ids.append(main_id)
                            total_main_placed += quantity
                            
                            # Small delay
                            time.sleep(0.3)
                        else:
                            main_id = f"TEST_MAIN_EXIT_{chunk_num}"
                            main_order_ids.append(main_id)
                            total_main_placed += quantity
                        
                        # 2. Place HEDGE SELL order (remove protection)
                        hedge_params = {
                            "tradingsymbol": hedge_symbol,
                            "exchange": exchange,
                            "transaction_type": "SELL",
                            "quantity": quantity,
                            "order_type": order_type,
                            "product": product,
                            "variety": "regular"
                        }
                        if order_type == "LIMIT" and hedge_price:
                            hedge_params["price"] = hedge_price
                            
                        if self.kite_client:
                            logger.info(f"  [HEDGE] Placing SELL {hedge_symbol} - {quantity} qty")
                            hedge_id = self.kite_client.kite.place_order(**hedge_params)
                            hedge_order_ids.append(hedge_id)
                            total_hedge_placed += quantity
                        else:
                            hedge_id = f"TEST_HEDGE_EXIT_{chunk_num}"
                            hedge_order_ids.append(hedge_id)
                            total_hedge_placed += quantity
                    
                    # Delay between chunks to avoid rate limiting
                    if i < len(lot_splits) - 1:
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"Failed to place chunk {chunk_num}: {e}")
                    failed_orders.append({
                        "chunk": chunk_num,
                        "lots": lots,
                        "error": str(e)
                    })
            
            # Prepare response
            result = {
                "status": "success" if not failed_orders else "partial",
                "action": action,
                "total_lots_requested": total_lots,
                "total_main_placed": total_main_placed // self.LOT_SIZE,
                "total_hedge_placed": total_hedge_placed // self.LOT_SIZE,
                "chunks_processed": len(lot_splits),
                "main_order_ids": main_order_ids,
                "hedge_order_ids": hedge_order_ids,
                "splits": lot_splits,
                "timestamp": datetime.now().isoformat()
            }
            
            if failed_orders:
                result["failed_orders"] = failed_orders
                result["message"] = f"Placed {len(main_order_ids)} of {len(lot_splits)} chunks"
            else:
                result["message"] = f"Successfully placed all {len(lot_splits)} chunks"
                
            logger.info(f"Hedged iceberg order completed: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"Error in hedged iceberg order: {e}")
            return {
                "status": "error",
                "message": str(e),
                "action": action,
                "total_lots_requested": total_lots,
                "timestamp": datetime.now().isoformat()
            }
    
    def validate_order_size(self, lots: int) -> tuple[bool, str]:
        """
        Validate if the order size is within limits
        
        Args:
            lots: Number of lots
            
        Returns:
            Tuple of (is_valid, message)
        """
        if lots <= 0:
            return False, "Lot size must be greater than 0"
            
        if lots > 100:
            return False, "Lot size exceeds maximum limit of 100 lots"
            
        if lots > self.MAX_LOTS_PER_ORDER:
            message = f"Order will be split into {len(self.calculate_order_splits(lots))} parts (max {self.MAX_LOTS_PER_ORDER} lots per order)"
            return True, message
            
        return True, "Order size is within limits"

# Singleton instance
_iceberg_service = None

def get_iceberg_service(kite_client=None):
    """Get or create iceberg order service instance"""
    global _iceberg_service
    if _iceberg_service is None:
        _iceberg_service = IcebergOrderService(kite_client)
    elif kite_client and not _iceberg_service.kite_client:
        _iceberg_service.kite_client = kite_client
    return _iceberg_service