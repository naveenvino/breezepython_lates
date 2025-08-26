"""
API Analyzer Service
Provides risk-free testing and validation of trading operations
"""

import json
import copy
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of validation checks"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]

@dataclass
class SimulationResult:
    """Result of order simulation"""
    entry_price: float
    estimated_exit_price: float
    position_size: int
    margin_required: float
    potential_profit: float
    potential_loss: float
    risk_reward_ratio: float
    execution_probability: float

@dataclass
class CostAnalysis:
    """Breakdown of trading costs"""
    brokerage: float
    stt: float
    exchange_fees: float
    gst: float
    stamp_duty: float
    total_charges: float
    breakeven_points: float

@dataclass
class AnalyzerReport:
    """Complete analyzer report"""
    validation: ValidationResult
    simulation: Optional[SimulationResult]
    costs: Optional[CostAnalysis]
    recommendations: List[str]
    risk_score: int  # 1-10, 10 being highest risk
    timestamp: datetime


class APIAnalyzer:
    """
    API Analyzer for risk-free testing of trading operations
    """
    
    def __init__(self):
        self.market_hours = {
            'start': timedelta(hours=9, minutes=15),
            'end': timedelta(hours=15, minutes=30)
        }
        self.lot_sizes = {
            'NIFTY': 75,
            'BANKNIFTY': 25,
            'FINNIFTY': 50,
            'MIDCAPNIFTY': 100
        }
        
    def analyze_order(self, order_request: Dict[str, Any]) -> AnalyzerReport:
        """
        Comprehensive analysis of an order without execution
        """
        # Ensure all required fields have default values
        order_request = {
            'symbol': order_request.get('symbol', ''),
            'quantity': order_request.get('quantity', 0),
            'side': order_request.get('side', 'BUY'),
            'order_type': order_request.get('order_type', 'MARKET'),
            'price': order_request.get('price', 100),
            'ltp': order_request.get('ltp', 100),
            'strike': order_request.get('strike'),
            'option_type': order_request.get('option_type'),
            'expiry': order_request.get('expiry'),
            'is_hedged': order_request.get('is_hedged', False),
            'trigger_price': order_request.get('trigger_price')
        }
        
        # Validate order parameters
        validation = self._validate_order(order_request)
        
        # Simulate execution if valid
        simulation = None
        if validation.is_valid:
            try:
                simulation = self._simulate_execution(order_request)
            except Exception as e:
                validation.errors.append(f"Simulation error: {str(e)}")
        
        # Calculate costs
        costs = None
        try:
            costs = self._calculate_costs(order_request)
        except Exception as e:
            validation.warnings.append(f"Cost calculation error: {str(e)}")
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            order_request, validation, simulation, costs
        )
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(order_request, simulation)
        
        return AnalyzerReport(
            validation=validation,
            simulation=simulation,
            costs=costs,
            recommendations=recommendations,
            risk_score=risk_score,
            timestamp=datetime.now()
        )
    
    def _validate_order(self, order: Dict[str, Any]) -> ValidationResult:
        """
        Validate order parameters
        """
        errors = []
        warnings = []
        suggestions = []
        
        # Required fields check
        required_fields = ['symbol', 'quantity', 'order_type', 'side']
        for field in required_fields:
            if field not in order or not order[field]:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return ValidationResult(False, errors, warnings, suggestions)
        
        # Symbol validation
        symbol = order['symbol']
        # Extract underlying from option symbol (e.g., "NFO:NIFTY25000CE" -> "NIFTY")
        underlying = None
        for key in self.lot_sizes.keys():
            if key in symbol.upper():
                underlying = key
                break
        
        if not underlying:
            warnings.append(f"Unknown underlying for symbol: {symbol}")
        
        # Quantity validation
        quantity = order.get('quantity')
        if quantity is None:
            quantity = 0
            
        if underlying and quantity > 0:
            lot_size = self.lot_sizes[underlying]
            if quantity % lot_size != 0:
                errors.append(f"Quantity must be multiple of lot size ({lot_size})")
            if quantity > lot_size * 50:  # Max 50 lots
                warnings.append("Large order size may impact execution")
        
        # Price validation for limit orders
        if order.get('order_type') == 'LIMIT':
            if 'price' not in order or order['price'] <= 0:
                errors.append("Limit order requires valid price")
        
        # Market hours check
        now = datetime.now()
        market_start = now.replace(hour=9, minute=15, second=0)
        market_end = now.replace(hour=15, minute=30, second=0)
        
        if not (market_start <= now <= market_end):
            warnings.append("Order placed outside market hours")
        
        # Options specific validation
        if 'strike' in order:
            self._validate_options_order(order, errors, warnings, suggestions)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _validate_options_order(self, order: Dict, errors: List, warnings: List, suggestions: List):
        """
        Additional validation for options orders
        """
        strike = order.get('strike', 0)
        option_type = order.get('option_type', '').upper() if order.get('option_type') else ''
        
        if option_type and option_type not in ['CE', 'PE']:
            errors.append("Option type must be CE or PE")
        
        # Strike validation
        if strike and strike % 50 != 0:  # NIFTY strikes are in multiples of 50
            errors.append("Strike price must be multiple of 50")
        
        # Expiry validation
        if 'expiry' not in order:
            warnings.append("No expiry specified, using current week")
        
        # Suggest hedging for naked options
        if order.get('side') == 'SELL' and not order.get('is_hedged'):
            suggestions.append("Consider hedging this position to limit risk")
    
    def _simulate_execution(self, order: Dict[str, Any]) -> SimulationResult:
        """
        Simulate order execution
        """
        symbol = order.get('symbol', '')
        quantity = order.get('quantity', 0) or 0
        side = order.get('side', 'BUY')
        
        # Simulate entry price
        if order.get('order_type') == 'MARKET':
            # Simulate slippage for market orders
            entry_price = order.get('ltp', 100) * (1.001 if side == 'BUY' else 0.999)
        else:
            entry_price = order.get('price', 100)
        
        # Calculate position metrics
        position_value = entry_price * quantity
        margin_required = position_value * 0.2  # 20% margin for options
        
        # Simulate potential outcomes
        if 'strike' in order:  # Options
            # Options specific simulation
            potential_profit = entry_price * quantity * 0.5  # 50% profit target
            potential_loss = entry_price * quantity * 0.3   # 30% stop loss
        else:  # Equity
            potential_profit = position_value * 0.02  # 2% profit target
            potential_loss = position_value * 0.01   # 1% stop loss
        
        # Calculate risk-reward ratio
        risk_reward = potential_profit / potential_loss if potential_loss > 0 else 0
        
        # Estimate execution probability
        execution_prob = self._estimate_execution_probability(order)
        
        return SimulationResult(
            entry_price=entry_price,
            estimated_exit_price=entry_price * 1.02,  # 2% profit target
            position_size=quantity,
            margin_required=margin_required,
            potential_profit=potential_profit,
            potential_loss=potential_loss,
            risk_reward_ratio=risk_reward,
            execution_probability=execution_prob
        )
    
    def _calculate_costs(self, order: Dict[str, Any]) -> CostAnalysis:
        """
        Calculate trading costs
        """
        quantity = order.get('quantity', 0) or 0
        price = order.get('price') or order.get('ltp', 100) or 100
        turnover = price * quantity
        
        # Brokerage (flat Rs 20 per order or 0.03% whichever is lower)
        brokerage = min(20, turnover * 0.0003) * 2  # Buy + Sell
        
        # STT (0.05% on sell for options)
        stt = turnover * 0.0005 if 'strike' in order else turnover * 0.001
        
        # Exchange fees (0.05% of turnover)
        exchange_fees = turnover * 0.0005
        
        # GST (18% on brokerage + exchange fees)
        gst = (brokerage + exchange_fees) * 0.18
        
        # Stamp duty (0.003% on buy)
        stamp_duty = turnover * 0.00003
        
        total_charges = brokerage + stt + exchange_fees + gst + stamp_duty
        
        # Breakeven points
        breakeven_points = (total_charges / quantity) if quantity > 0 else 0
        
        return CostAnalysis(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_fees=round(exchange_fees, 2),
            gst=round(gst, 2),
            stamp_duty=round(stamp_duty, 2),
            total_charges=round(total_charges, 2),
            breakeven_points=round(breakeven_points, 2)
        )
    
    def _generate_recommendations(self, order: Dict, validation: ValidationResult, 
                                 simulation: Optional[SimulationResult], 
                                 costs: Optional[CostAnalysis]) -> List[str]:
        """
        Generate trading recommendations
        """
        recommendations = []
        
        # Based on validation
        if validation.warnings:
            recommendations.append("Review warnings before placing order")
        
        # Based on simulation
        if simulation:
            if simulation.risk_reward_ratio < 1.5:
                recommendations.append("Risk-reward ratio is low, consider adjusting targets")
            
            if simulation.execution_probability < 0.7:
                recommendations.append("Low execution probability, consider limit order")
            
            if simulation.margin_required > 100000:
                recommendations.append("High margin requirement, ensure sufficient funds")
        
        # Based on costs
        if costs and costs.total_charges > 100:
            recommendations.append("High transaction costs, consider larger position size")
        
        # Options specific
        if 'strike' in order:
            if order.get('side') == 'SELL' and not order.get('is_hedged'):
                recommendations.append("URGENT: Hedge this position to limit max loss")
            
            if 'expiry' in order:
                if order.get('expiry'):
                    days_to_expiry = (datetime.strptime(order['expiry'], '%Y-%m-%d') - datetime.now()).days
                else:
                    days_to_expiry = 7  # Default to weekly expiry
                if days_to_expiry <= 2:
                    recommendations.append("Near expiry - high theta decay risk")
        
        # Time based
        now = datetime.now()
        if now.hour >= 15:
            recommendations.append("Close to market closing, consider next day execution")
        
        return recommendations
    
    def _calculate_risk_score(self, order: Dict, simulation: Optional[SimulationResult]) -> int:
        """
        Calculate risk score (1-10, 10 being highest risk)
        """
        risk_score = 5  # Base score
        
        # Order size risk
        if order.get('quantity', 0) > 1000:
            risk_score += 2
        
        # Naked options risk
        if 'strike' in order and order.get('side') == 'SELL' and not order.get('is_hedged'):
            risk_score += 3
        
        # Market order risk
        if order.get('order_type') == 'MARKET':
            risk_score += 1
        
        # Risk-reward assessment
        if simulation and simulation.risk_reward_ratio < 1:
            risk_score += 2
        
        # Cap at 10
        return min(risk_score, 10)
    
    def _estimate_execution_probability(self, order: Dict) -> float:
        """
        Estimate probability of successful execution
        """
        prob = 0.5  # Base probability
        
        # Market orders have high execution probability
        if order.get('order_type') == 'MARKET':
            prob = 0.95
        
        # Limit orders depend on price
        elif order.get('order_type') == 'LIMIT':
            # Compare with LTP
            ltp = order.get('ltp', 100)
            limit_price = order.get('price', ltp)
            
            if order.get('side') == 'BUY':
                if limit_price >= ltp:
                    prob = 0.9
                else:
                    prob = 0.6
            else:  # SELL
                if limit_price <= ltp:
                    prob = 0.9
                else:
                    prob = 0.6
        
        return prob
    
    def analyze_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a complete trading strategy
        """
        results = {
            'orders': [],
            'total_margin': 0,
            'total_risk': 0,
            'total_reward': 0,
            'overall_risk_score': 0,
            'strategy_recommendations': []
        }
        
        # Analyze each order in the strategy
        for order in strategy.get('orders', []):
            analysis = self.analyze_order(order)
            results['orders'].append({
                'order': order,
                'analysis': asdict(analysis)
            })
            
            if analysis.simulation:
                results['total_margin'] += analysis.simulation.margin_required
                results['total_risk'] += analysis.simulation.potential_loss
                results['total_reward'] += analysis.simulation.potential_profit
        
        # Calculate overall metrics
        if results['total_risk'] > 0:
            results['overall_rr_ratio'] = results['total_reward'] / results['total_risk']
        
        # Strategy level recommendations
        if results['total_margin'] > 500000:
            results['strategy_recommendations'].append("High margin requirement for strategy")
        
        if len(strategy.get('orders', [])) > 10:
            results['strategy_recommendations'].append("Complex strategy - consider simplifying")
        
        return results
    
    def export_report(self, report: AnalyzerReport, format: str = 'json') -> str:
        """
        Export analyzer report in various formats
        """
        if format == 'json':
            return json.dumps(asdict(report), default=str, indent=2)
        elif format == 'text':
            return self._format_text_report(report)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_text_report(self, report: AnalyzerReport) -> str:
        """
        Format report as readable text
        """
        lines = [
            "=" * 50,
            "API ANALYZER REPORT",
            "=" * 50,
            f"Generated: {report.timestamp}",
            f"Risk Score: {report.risk_score}/10",
            ""
        ]
        
        # Validation section
        lines.append("VALIDATION:")
        lines.append(f"  Status: {'PASSED' if report.validation.is_valid else 'FAILED'}")
        if report.validation.errors:
            lines.append("  Errors:")
            for error in report.validation.errors:
                lines.append(f"    - {error}")
        if report.validation.warnings:
            lines.append("  Warnings:")
            for warning in report.validation.warnings:
                lines.append(f"    - {warning}")
        
        # Simulation section
        if report.simulation:
            lines.append("\nSIMULATION:")
            lines.append(f"  Entry Price: {report.simulation.entry_price}")
            lines.append(f"  Margin Required: ₹{report.simulation.margin_required:,.2f}")
            lines.append(f"  Potential Profit: ₹{report.simulation.potential_profit:,.2f}")
            lines.append(f"  Potential Loss: ₹{report.simulation.potential_loss:,.2f}")
            lines.append(f"  Risk-Reward Ratio: {report.simulation.risk_reward_ratio:.2f}")
            lines.append(f"  Execution Probability: {report.simulation.execution_probability*100:.1f}%")
        
        # Costs section
        if report.costs:
            lines.append("\nCOSTS:")
            lines.append(f"  Brokerage: ₹{report.costs.brokerage}")
            lines.append(f"  STT: ₹{report.costs.stt}")
            lines.append(f"  Total Charges: ₹{report.costs.total_charges}")
            lines.append(f"  Breakeven Points: {report.costs.breakeven_points}")
        
        # Recommendations
        if report.recommendations:
            lines.append("\nRECOMMENDATIONS:")
            for rec in report.recommendations:
                lines.append(f"  • {rec}")
        
        lines.append("=" * 50)
        return "\n".join(lines)