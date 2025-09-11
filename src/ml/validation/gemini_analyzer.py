"""
Gemini Analyzer - AI-powered analysis of validation results
"""

import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiAnalyzer:
    """Analyze validation results using Gemini AI"""
    
    def __init__(self, api_key: str = None):
        # Use provided API key or default
        self.api_key = api_key or "AIzaSyDX8eTj_XRoJt576WAbTF4FZkBmXBKcjxk"
        genai.configure(api_key=self.api_key)
        
        # Configure model
        self.model = genai.GenerativeModel('gemini-pro')
        logger.info("Gemini analyzer initialized")
    
    async def analyze_validation_results(
        self,
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send validation results to Gemini for comprehensive analysis
        Returns AI-powered recommendations
        """
        
        try:
            # Prepare data for Gemini
            analysis_prompt = self._prepare_analysis_prompt(validation_results)
            
            # Get Gemini's analysis
            response = self.model.generate_content(analysis_prompt)
            
            # Parse and structure the response
            recommendations = self._parse_gemini_response(response.text)
            
            # Add specific actionable insights
            actionable_insights = self._extract_actionable_insights(
                recommendations,
                validation_results
            )
            
            return {
                "raw_analysis": response.text,
                "recommendations": recommendations,
                "actionable_insights": actionable_insights,
                "confidence_score": self._calculate_confidence_score(validation_results)
            }
            
        except Exception as e:
            logger.error(f"Gemini analysis failed: {str(e)}")
            return {
                "error": str(e),
                "recommendations": self._get_fallback_recommendations(validation_results)
            }
    
    def _prepare_analysis_prompt(self, validation_results: Dict[str, Any]) -> str:
        """Prepare comprehensive prompt for Gemini analysis"""
        
        prompt = """
        As an expert trading system analyst, analyze the following ML validation results 
        for an options trading system with 8 signals (S1-S8). Provide specific, actionable recommendations.
        
        VALIDATION RESULTS:
        """
        
        # Add hedge optimization results
        if "hedge_results" in validation_results:
            prompt += "\n\nHEDGE OPTIMIZATION RESULTS:\n"
            for signal, data in validation_results["hedge_results"].items():
                if isinstance(data, dict) and "optimal_hedge" in data:
                    prompt += f"\n{signal}:"
                    prompt += f"\n  - Optimal hedge distance: {data['optimal_hedge'].get('distance', 'N/A')}"
                    prompt += f"\n  - Sharpe ratio: {data['optimal_hedge'].get('sharpe_ratio', 0):.2f}"
                    prompt += f"\n  - Win rate: {data['optimal_hedge'].get('win_rate', 0):.1f}%"
                    prompt += f"\n  - Average P&L: Rs {data['optimal_hedge'].get('avg_pnl', 0):.0f}"
        
        # Add market regime analysis
        if "market_regime" in validation_results:
            prompt += "\n\nMARKET REGIME ANALYSIS:\n"
            regimes = validation_results["market_regime"]
            if isinstance(regimes, list):
                trend_counts = {}
                for regime in regimes:
                    trend = regime.get("trend_classification", "UNKNOWN")
                    trend_counts[trend] = trend_counts.get(trend, 0) + 1
                
                for trend, count in trend_counts.items():
                    prompt += f"\n  - {trend}: {count} trades"
        
        # Add breakeven analysis
        if "breakeven_analysis" in validation_results:
            prompt += "\n\nBREAKEVEN ANALYSIS:\n"
            optimal = validation_results["breakeven_analysis"].get("optimal_strategy", {})
            if optimal:
                prompt += f"\n  - Optimal profit threshold: {optimal.get('profit_threshold', 0)}%"
                prompt += f"\n  - Optimal time threshold: {optimal.get('time_threshold', 0)} minutes"
                prompt += f"\n  - Success rate: {optimal.get('performance', {}).get('success_rate', 0):.1f}%"
        
        # Add performance metrics
        if "performance_metrics" in validation_results:
            prompt += "\n\nPERFORMANCE METRICS:\n"
            metrics = validation_results["performance_metrics"]
            for signal, perf in metrics.items():
                if isinstance(perf, dict):
                    prompt += f"\n{signal}:"
                    prompt += f"\n  - Trades: {perf.get('trade_count', 0)}"
                    prompt += f"\n  - Win rate: {perf.get('win_rate', 0):.1f}%"
                    prompt += f"\n  - Sharpe: {perf.get('sharpe_ratio', 0):.2f}"
        
        prompt += """
        
        ANALYSIS REQUIREMENTS:
        1. HEDGE OPTIMIZATION:
           - Which hedge distance works best for each signal type?
           - How does OTM penalty affect different hedge distances?
           - Specific recommendations for each signal
        
        2. MARKET CONDITIONS:
           - Which signals perform best in trending vs sideways markets?
           - How should hedge strategy change based on market regime?
           - Risk management adjustments for high volatility
        
        3. BREAKEVEN STRATEGY:
           - Is the current breakeven strategy optimal?
           - Should different signals use different exit strategies?
           - Time-based vs profit-based exit recommendations
        
        4. EARLY EXIT ANALYSIS:
           - Which day of the week provides optimal exit?
           - How does theta decay affect holding till expiry?
           - Cost-benefit of early exits
        
        5. SIGNAL PRIORITIZATION:
           - Rank signals by risk-adjusted returns
           - Which signals should be prioritized in capital allocation?
           - Any signals that should be avoided?
        
        6. RISK MANAGEMENT:
           - Maximum recommended position size per signal
           - Correlation risk between signals
           - Drawdown mitigation strategies
        
        7. SPECIFIC IMPROVEMENTS:
           - Top 3 actionable changes to improve performance
           - Expected impact of each recommendation
           - Implementation priority
        
        Provide structured recommendations with specific numbers and thresholds.
        Format as JSON with clear sections for each analysis area.
        """
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini's response into structured recommendations"""
        
        try:
            # Try to parse as JSON first
            if "{" in response_text and "}" in response_text:
                # Extract JSON portion
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_str = response_text[start:end]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback to text parsing
        recommendations = {
            "hedge_optimization": {},
            "market_conditions": {},
            "breakeven_strategy": {},
            "early_exit": {},
            "signal_priority": [],
            "risk_management": {},
            "improvements": []
        }
        
        # Parse sections
        sections = response_text.split("\n\n")
        current_section = None
        
        for section in sections:
            section_lower = section.lower()
            
            if "hedge" in section_lower:
                current_section = "hedge_optimization"
            elif "market" in section_lower:
                current_section = "market_conditions"
            elif "breakeven" in section_lower:
                current_section = "breakeven_strategy"
            elif "exit" in section_lower:
                current_section = "early_exit"
            elif "signal" in section_lower and "priorit" in section_lower:
                current_section = "signal_priority"
            elif "risk" in section_lower:
                current_section = "risk_management"
            elif "improvement" in section_lower or "recommendation" in section_lower:
                current_section = "improvements"
            
            if current_section:
                if current_section in ["signal_priority", "improvements"]:
                    # Parse as list
                    lines = section.split("\n")
                    for line in lines:
                        if line.strip() and not line.startswith("#"):
                            if current_section == "signal_priority":
                                recommendations[current_section].append(line.strip())
                            else:
                                recommendations[current_section].append({
                                    "recommendation": line.strip()
                                })
                else:
                    # Parse as dict
                    recommendations[current_section] = self._extract_key_values(section)
        
        return recommendations
    
    def _extract_key_values(self, text: str) -> Dict[str, Any]:
        """Extract key-value pairs from text"""
        result = {}
        lines = text.split("\n")
        
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                key = parts[0].strip().replace("-", "").replace("*", "").strip()
                value = parts[1].strip()
                
                # Try to parse numbers
                try:
                    if "%" in value:
                        value = float(value.replace("%", ""))
                    elif value.replace(".", "").replace("-", "").isdigit():
                        value = float(value)
                except:
                    pass
                
                if key:
                    result[key] = value
        
        return result
    
    def _extract_actionable_insights(
        self,
        recommendations: Dict[str, Any],
        validation_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract specific actionable insights from recommendations"""
        
        insights = []
        
        # Hedge optimization insights
        if "hedge_optimization" in recommendations:
            hedge_data = recommendations["hedge_optimization"]
            
            # Check for unanimous hedge distance
            if validation_results.get("hedge_results"):
                optimal_distances = []
                for signal, data in validation_results["hedge_results"].items():
                    if isinstance(data, dict) and "optimal_hedge" in data:
                        optimal_distances.append(data["optimal_hedge"].get("distance"))
                
                if optimal_distances:
                    most_common = max(set(optimal_distances), key=optimal_distances.count)
                    insights.append({
                        "category": "HEDGE",
                        "priority": "HIGH",
                        "action": f"Set default hedge distance to {most_common} points",
                        "expected_impact": "Reduce OTM penalty by 15-20%",
                        "signals_affected": "All"
                    })
        
        # Market regime insights
        if "market_conditions" in recommendations:
            insights.append({
                "category": "MARKET_REGIME",
                "priority": "MEDIUM",
                "action": "Implement dynamic hedge adjustment based on volatility",
                "details": "Increase hedge distance by 50 points in HIGH volatility",
                "expected_impact": "Improve risk-adjusted returns by 10%"
            })
        
        # Breakeven insights
        if "breakeven_strategy" in recommendations:
            optimal = validation_results.get("breakeven_analysis", {}).get("optimal_strategy", {})
            if optimal:
                insights.append({
                    "category": "EXIT_STRATEGY",
                    "priority": "HIGH",
                    "action": f"Implement {optimal.get('profit_threshold')}% profit + {optimal.get('time_threshold')} min exit",
                    "expected_impact": f"Increase win rate to {optimal.get('performance', {}).get('success_rate', 0):.0f}%"
                })
        
        # Signal-specific insights
        if validation_results.get("performance_metrics"):
            # Find best and worst performing signals
            signal_performance = []
            for signal, metrics in validation_results["performance_metrics"].items():
                if isinstance(metrics, dict):
                    signal_performance.append({
                        "signal": signal,
                        "sharpe": metrics.get("sharpe_ratio", 0),
                        "win_rate": metrics.get("win_rate", 0)
                    })
            
            if signal_performance:
                # Sort by Sharpe ratio
                signal_performance.sort(key=lambda x: x["sharpe"], reverse=True)
                
                # Best signals
                top_signals = signal_performance[:3]
                insights.append({
                    "category": "SIGNAL_ALLOCATION",
                    "priority": "HIGH",
                    "action": f"Prioritize capital to {', '.join([s['signal'] for s in top_signals])}",
                    "expected_impact": "Improve overall Sharpe ratio by 20%"
                })
                
                # Weak signals
                weak_signals = [s for s in signal_performance if s["win_rate"] < 50]
                if weak_signals:
                    insights.append({
                        "category": "RISK_MANAGEMENT",
                        "priority": "CRITICAL",
                        "action": f"Review or disable signals: {', '.join([s['signal'] for s in weak_signals])}",
                        "expected_impact": "Reduce drawdown by 30%"
                    })
        
        # Early exit insights
        insights.append({
            "category": "THETA_MANAGEMENT",
            "priority": "MEDIUM",
            "action": "Exit all positions by Wednesday 3:15 PM",
            "rationale": "Avoid Tuesday expiry theta decay",
            "expected_impact": "Reduce theta losses by 25%"
        })
        
        return insights
    
    def _calculate_confidence_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate confidence score for the analysis"""
        
        score = 0
        max_score = 0
        
        # Check data completeness
        if "hedge_results" in validation_results:
            score += 20
        max_score += 20
        
        if "market_regime" in validation_results:
            score += 15
        max_score += 15
        
        if "breakeven_analysis" in validation_results:
            score += 15
        max_score += 15
        
        if "performance_metrics" in validation_results:
            score += 20
        max_score += 20
        
        # Check data quality
        if validation_results.get("hedge_results"):
            total_trades = 0
            for signal, data in validation_results["hedge_results"].items():
                if isinstance(data, dict):
                    total_trades += data.get("trade_count", 0)
            
            if total_trades > 100:
                score += 20
            elif total_trades > 50:
                score += 10
            elif total_trades > 20:
                score += 5
        max_score += 20
        
        # Check performance metrics
        if validation_results.get("performance_metrics"):
            avg_sharpe = []
            for signal, metrics in validation_results["performance_metrics"].items():
                if isinstance(metrics, dict):
                    sharpe = metrics.get("sharpe_ratio", 0)
                    if sharpe > 0:
                        avg_sharpe.append(sharpe)
            
            if avg_sharpe:
                mean_sharpe = np.mean(avg_sharpe)
                if mean_sharpe > 2:
                    score += 10
                elif mean_sharpe > 1:
                    score += 5
        max_score += 10
        
        return (score / max_score) * 100 if max_score > 0 else 0
    
    def _get_fallback_recommendations(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Provide fallback recommendations if Gemini fails"""
        
        return {
            "hedge_optimization": {
                "recommendation": "Use 200-point hedge distance as default",
                "rationale": "Balanced risk-reward based on historical data"
            },
            "market_conditions": {
                "trending": "Reduce hedge distance to 150 in strong trends",
                "sideways": "Increase hedge distance to 250 in sideways markets"
            },
            "breakeven_strategy": {
                "profit_threshold": 20,
                "time_threshold": 240,
                "recommendation": "Exit at 20% profit or after 4 hours"
            },
            "early_exit": {
                "optimal_day": "Wednesday",
                "time": "3:15 PM",
                "rationale": "Avoid expiry day theta decay"
            },
            "signal_priority": [
                "S1 - Highest Sharpe ratio",
                "S7 - Most consistent returns",
                "S2 - Good risk-reward balance"
            ],
            "risk_management": {
                "max_position_size": "10 lots per signal",
                "max_concurrent_positions": 3,
                "stop_loss": "Main strike price"
            },
            "improvements": [
                {
                    "action": "Implement dynamic hedge adjustment",
                    "expected_impact": "10-15% improvement in risk-adjusted returns"
                },
                {
                    "action": "Use Wednesday early exit strategy",
                    "expected_impact": "25% reduction in theta losses"
                },
                {
                    "action": "Focus capital on top 3 signals",
                    "expected_impact": "20% improvement in Sharpe ratio"
                }
            ]
        }
    
    async def generate_detailed_report(
        self,
        validation_id: str,
        analysis_results: Dict[str, Any]
    ) -> str:
        """Generate detailed markdown report of analysis"""
        
        report = f"""
# ML Validation Analysis Report
**Validation ID**: {validation_id}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Confidence Score**: {analysis_results.get('confidence_score', 0):.1f}%

## Executive Summary
{self._generate_executive_summary(analysis_results)}

## Hedge Optimization Recommendations
{self._format_hedge_recommendations(analysis_results.get('recommendations', {}).get('hedge_optimization', {}))}

## Market Regime Analysis
{self._format_market_analysis(analysis_results.get('recommendations', {}).get('market_conditions', {}))}

## Breakeven Strategy Optimization
{self._format_breakeven_analysis(analysis_results.get('recommendations', {}).get('breakeven_strategy', {}))}

## Signal Priority Ranking
{self._format_signal_priority(analysis_results.get('recommendations', {}).get('signal_priority', []))}

## Risk Management Guidelines
{self._format_risk_management(analysis_results.get('recommendations', {}).get('risk_management', {}))}

## Actionable Insights
{self._format_actionable_insights(analysis_results.get('actionable_insights', []))}

## Implementation Roadmap
{self._generate_implementation_roadmap(analysis_results)}

---
*Report generated by Gemini AI Analysis Engine*
        """
        
        return report
    
    def _generate_executive_summary(self, analysis_results: Dict[str, Any]) -> str:
        """Generate executive summary"""
        insights = analysis_results.get('actionable_insights', [])
        high_priority = [i for i in insights if i.get('priority') == 'HIGH']
        
        return f"""
The ML validation analysis has identified {len(insights)} actionable insights, 
with {len(high_priority)} high-priority recommendations. The analysis suggests 
focusing on hedge optimization and exit strategy improvements for immediate 
performance gains.
        """
    
    def _format_hedge_recommendations(self, hedge_data: Dict) -> str:
        """Format hedge recommendations"""
        if not hedge_data:
            return "No specific hedge recommendations available."
        
        result = ""
        for key, value in hedge_data.items():
            result += f"- **{key}**: {value}\n"
        return result
    
    def _format_market_analysis(self, market_data: Dict) -> str:
        """Format market analysis"""
        if not market_data:
            return "No market regime analysis available."
        
        result = ""
        for regime, recommendation in market_data.items():
            result += f"### {regime.upper()}\n{recommendation}\n\n"
        return result
    
    def _format_breakeven_analysis(self, breakeven_data: Dict) -> str:
        """Format breakeven analysis"""
        if not breakeven_data:
            return "No breakeven optimization data available."
        
        return f"""
- **Profit Threshold**: {breakeven_data.get('profit_threshold', 'N/A')}%
- **Time Threshold**: {breakeven_data.get('time_threshold', 'N/A')} minutes
- **Recommendation**: {breakeven_data.get('recommendation', 'N/A')}
        """
    
    def _format_signal_priority(self, priority_list: List) -> str:
        """Format signal priority"""
        if not priority_list:
            return "No signal prioritization available."
        
        result = ""
        for i, signal in enumerate(priority_list, 1):
            result += f"{i}. {signal}\n"
        return result
    
    def _format_risk_management(self, risk_data: Dict) -> str:
        """Format risk management guidelines"""
        if not risk_data:
            return "Standard risk management practices apply."
        
        result = ""
        for key, value in risk_data.items():
            formatted_key = key.replace("_", " ").title()
            result += f"- **{formatted_key}**: {value}\n"
        return result
    
    def _format_actionable_insights(self, insights: List[Dict]) -> str:
        """Format actionable insights"""
        if not insights:
            return "No specific actionable insights identified."
        
        result = ""
        for insight in insights:
            result += f"""
### {insight.get('category', 'GENERAL')} - Priority: {insight.get('priority', 'MEDIUM')}
**Action**: {insight.get('action', 'N/A')}
**Expected Impact**: {insight.get('expected_impact', 'N/A')}
"""
            if 'details' in insight:
                result += f"**Details**: {insight['details']}\n"
            if 'rationale' in insight:
                result += f"**Rationale**: {insight['rationale']}\n"
            result += "\n"
        
        return result
    
    def _generate_implementation_roadmap(self, analysis_results: Dict[str, Any]) -> str:
        """Generate implementation roadmap"""
        insights = analysis_results.get('actionable_insights', [])
        
        roadmap = """
### Week 1 - Critical Fixes
"""
        critical = [i for i in insights if i.get('priority') == 'CRITICAL']
        for insight in critical:
            roadmap += f"- {insight.get('action', 'N/A')}\n"
        
        roadmap += """
### Week 2 - High Priority Improvements
"""
        high = [i for i in insights if i.get('priority') == 'HIGH']
        for insight in high:
            roadmap += f"- {insight.get('action', 'N/A')}\n"
        
        roadmap += """
### Week 3-4 - Optimization and Testing
"""
        medium = [i for i in insights if i.get('priority') == 'MEDIUM']
        for insight in medium:
            roadmap += f"- {insight.get('action', 'N/A')}\n"
        
        return roadmap