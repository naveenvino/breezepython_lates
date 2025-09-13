"""
Dynamic Exit Manager Service
Reads current exit configuration from database for active positions
Exit timing follows TODAY'S settings, not entry-time settings
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class DynamicExitManager:
    """Manages position exits based on CURRENT configuration settings"""

    def __init__(self, kite_client=None):
        self.kite_client = kite_client
        self.is_monitoring = False

    def get_current_exit_config(self) -> Dict:
        """
        Get the CURRENT exit configuration from database
        This is read LIVE, not stored at entry time
        """
        try:
            db_path = Path("data/trading_settings.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get current exit timing settings
            cursor.execute("""
                SELECT exit_day_offset, exit_time, auto_square_off_enabled
                FROM TradeConfiguration
                WHERE user_id='default' AND config_name='default'
                ORDER BY id DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    "exit_day_offset": result[0] if result[0] is not None else 0,  # T+0 default
                    "exit_time": result[1] if result[1] else "15:15",
                    "auto_square_off_enabled": bool(result[2]) if len(result) > 2 else True
                }
            else:
                # Default configuration
                return {
                    "exit_day_offset": 0,  # Same day
                    "exit_time": "15:15",  # 3:15 PM
                    "auto_square_off_enabled": True
                }

        except Exception as e:
            logger.error(f"Error getting current exit config: {e}")
            return {
                "exit_day_offset": 0,
                "exit_time": "15:15",
                "auto_square_off_enabled": True
            }

    def calculate_exit_time_for_position(self, entry_time: datetime) -> datetime:
        """
        Calculate exit time based on CURRENT settings, not entry-time settings

        Args:
            entry_time: When the position was entered

        Returns:
            datetime: When the position should exit based on TODAY'S configuration
        """
        # Get TODAY'S configuration
        config = self.get_current_exit_config()

        if not config['auto_square_off_enabled']:
            return None

        exit_day_offset = config['exit_day_offset']
        exit_time_str = config['exit_time']

        # Calculate exit date from entry date + current offset setting
        exit_date = entry_time.date() + timedelta(days=exit_day_offset)

        # Handle weekends (market closed)
        while exit_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            exit_date += timedelta(days=1)

        # Parse exit time
        hour, minute = map(int, exit_time_str.split(':'))
        exit_datetime = datetime.combine(exit_date, datetime.min.time().replace(hour=hour, minute=minute))

        logger.info(f"Position entered at {entry_time}, will exit at {exit_datetime} based on CURRENT settings (T+{exit_day_offset})")

        return exit_datetime

    def get_positions_to_exit_now(self) -> List[Dict]:
        """
        Check all active positions and return those that should exit based on CURRENT settings
        """
        positions_to_exit = []

        try:
            db_path = Path("data/trading_settings.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get all active positions
            cursor.execute("""
                SELECT webhook_id, main_symbol, hedge_symbol, entry_time,
                       main_order_id, hedge_order_id, lots, option_type
                FROM OrderTracking
                WHERE status IN ('active', 'executed', 'ACTIVE', 'EXECUTED')
                  AND (exit_time IS NULL OR exit_time = '')
            """)

            active_positions = cursor.fetchall()
            conn.close()

            current_time = datetime.now()

            for position in active_positions:
                webhook_id, main_symbol, hedge_symbol, entry_time_str, main_order, hedge_order, lots, option_type = position

                # Parse entry time
                entry_time = datetime.fromisoformat(entry_time_str) if entry_time_str else datetime.now()

                # Calculate exit time based on CURRENT settings
                exit_time = self.calculate_exit_time_for_position(entry_time)

                if exit_time and current_time >= exit_time:
                    positions_to_exit.append({
                        "webhook_id": webhook_id,
                        "main_symbol": main_symbol,
                        "hedge_symbol": hedge_symbol,
                        "main_order_id": main_order,
                        "hedge_order_id": hedge_order,
                        "lots": lots,
                        "option_type": option_type,
                        "reason": f"Auto square-off at {exit_time.strftime('%H:%M')}"
                    })

            if positions_to_exit:
                logger.info(f"Found {len(positions_to_exit)} positions to exit based on CURRENT settings")

        except Exception as e:
            logger.error(f"Error checking positions to exit: {e}")

        return positions_to_exit

    async def monitor_and_exit(self):
        """
        Continuous monitoring loop that checks CURRENT settings
        """
        logger.info("Starting dynamic exit monitoring with LIVE configuration reading")

        while self.is_monitoring:
            try:
                # Check positions every minute
                positions_to_exit = self.get_positions_to_exit_now()

                for position in positions_to_exit:
                    await self.execute_square_off(position)

                # Wait 60 seconds before next check
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    async def execute_square_off(self, position: Dict):
        """Execute the square-off for a position"""
        try:
            if not self.kite_client:
                logger.error("Kite client not initialized")
                return

            logger.info(f"Executing square-off for {position['main_symbol']}")

            # Square off main position
            if position['main_order_id']:
                main_result = await self.kite_client.square_off_position(
                    symbol=position['main_symbol'],
                    quantity=position['lots'] * 75,  # Assuming 75 qty per lot
                    transaction_type='BUY' if position['option_type'] == 'PE' else 'SELL'
                )
                logger.info(f"Main position squared off: {main_result}")

            # Square off hedge if exists
            if position['hedge_symbol'] and position['hedge_order_id']:
                hedge_result = await self.kite_client.square_off_position(
                    symbol=position['hedge_symbol'],
                    quantity=position['lots'] * 75,
                    transaction_type='SELL' if position['option_type'] == 'PE' else 'BUY'
                )
                logger.info(f"Hedge position squared off: {hedge_result}")

            # Update database
            self.update_position_status(position['webhook_id'], 'squared_off', position['reason'])

        except Exception as e:
            logger.error(f"Error executing square-off: {e}")

    def update_position_status(self, webhook_id: str, status: str, reason: str):
        """Update position status in database"""
        try:
            db_path = Path("data/trading_settings.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE OrderTracking
                SET status = ?, exit_reason = ?, exit_time = ?
                WHERE webhook_id = ?
            """, (status, reason, datetime.now().isoformat(), webhook_id))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating position status: {e}")

# Singleton instance
_exit_manager = None

def get_dynamic_exit_manager(kite_client=None):
    """Get or create the dynamic exit manager instance"""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = DynamicExitManager(kite_client)
    return _exit_manager