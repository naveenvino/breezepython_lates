"""
Hybrid Exit Manager - Combines ML predictions with Progressive P&L Stop-Loss
"""

import logging
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ExitDecisionType(Enum):
    """Types of exit decisions"""
    ML_PREDICTED = "ML_PREDICTED"
    PROGRESSIVE_SL = "PROGRESSIVE_SL"
    HYBRID_CONSENSUS = "HYBRID_CONSENSUS"
    INDEX_STOP_LOSS = "INDEX_STOP_LOSS"
    TIME_EXIT = "TIME_EXIT"
    EXPIRY = "EXPIRY"


@dataclass
class ExitDecision:
    """Exit decision with attribution"""
    should_exit: bool
    decision_type: ExitDecisionType
    confidence: float
    reason: str
    exit_price: Optional[float] = None
    partial_exit_percent: Optional[float] = None
    
    
class HybridExitManager:
    """
    Manages exit decisions by combining ML predictions with progressive P&L stop-loss rules.
    Provides hybrid decision logic for robust risk management.
    """
    
    def __init__(
        self,
        ml_confidence_threshold: float = 0.7,
        prefer_ml_when_confident: bool = True,
        track_decision_attribution: bool = True
    ):
        """
        Initialize Hybrid Exit Manager
        
        Args:
            ml_confidence_threshold: Minimum ML confidence to trust predictions
            prefer_ml_when_confident: Prefer ML over rules when confidence is high
            track_decision_attribution: Track which system made each decision
        """
        self.ml_confidence_threshold = ml_confidence_threshold
        self.prefer_ml_when_confident = prefer_ml_when_confident
        self.track_decision_attribution = track_decision_attribution
        
        # Decision tracking
        self.decision_history = []
        self.ml_accuracy_tracker = {"correct": 0, "incorrect": 0}
        self.rule_accuracy_tracker = {"correct": 0, "incorrect": 0}
        
    def make_exit_decision(
        self,
        ml_exit_prediction: Dict,
        progressive_sl_status: Dict,
        current_pnl: float,
        current_time: datetime,
        trade_entry_time: datetime,
        max_profit_seen: float = 0
    ) -> ExitDecision:
        """
        Make hybrid exit decision combining ML and progressive SL
        
        Args:
            ml_exit_prediction: ML model's exit prediction with confidence
            progressive_sl_status: Progressive SL manager's status
            current_pnl: Current P&L of the position
            current_time: Current timestamp
            trade_entry_time: Trade entry timestamp
            max_profit_seen: Maximum profit seen so far
            
        Returns:
            ExitDecision with attribution
        """
        
        # Extract ML prediction details
        ml_should_exit = ml_exit_prediction.get("should_exit", False)
        ml_confidence = ml_exit_prediction.get("confidence", 0.0)
        ml_reason = ml_exit_prediction.get("reason", "ML prediction")
        ml_partial_exit = ml_exit_prediction.get("partial_exit_percent", None)
        
        # Extract progressive SL status
        psl_hit = progressive_sl_status.get("sl_hit", False)
        psl_reason = progressive_sl_status.get("reason", "")
        psl_stage = progressive_sl_status.get("stage", "INITIAL")
        
        # Decision logic
        decision = None
        
        # Priority 1: Progressive SL hit (safety first)
        if psl_hit:
            decision = ExitDecision(
                should_exit=True,
                decision_type=ExitDecisionType.PROGRESSIVE_SL,
                confidence=1.0,
                reason=psl_reason
            )
            
        # Priority 2: High confidence ML prediction
        elif ml_should_exit and ml_confidence >= self.ml_confidence_threshold:
            if self.prefer_ml_when_confident:
                decision = ExitDecision(
                    should_exit=True,
                    decision_type=ExitDecisionType.ML_PREDICTED,
                    confidence=ml_confidence,
                    reason=ml_reason,
                    partial_exit_percent=ml_partial_exit
                )
            else:
                # Even with high ML confidence, check consensus
                decision = self._check_consensus(
                    ml_should_exit, ml_confidence, psl_stage, 
                    current_pnl, max_profit_seen
                )
                
        # Priority 3: Consensus decision for borderline cases
        elif ml_confidence >= 0.5:  # Medium confidence
            decision = self._check_consensus(
                ml_should_exit, ml_confidence, psl_stage,
                current_pnl, max_profit_seen
            )
            
        # Priority 4: No exit
        if decision is None:
            decision = ExitDecision(
                should_exit=False,
                decision_type=ExitDecisionType.HYBRID_CONSENSUS,
                confidence=1.0 - ml_confidence,
                reason="Both ML and Progressive SL suggest holding"
            )
            
        # Track decision
        if self.track_decision_attribution:
            self._track_decision(decision, current_time, current_pnl)
            
        return decision
        
    def _check_consensus(
        self,
        ml_exit: bool,
        ml_confidence: float,
        psl_stage: str,
        current_pnl: float,
        max_profit_seen: float
    ) -> ExitDecision:
        """
        Check consensus between ML and progressive SL for borderline cases
        
        Returns:
            Consensus-based exit decision
        """
        consensus_factors = []
        
        # Factor 1: ML suggests exit
        if ml_exit:
            consensus_factors.append(("ml_exit", ml_confidence))
            
        # Factor 2: Progressive SL in advanced stage
        if psl_stage in ["BREAKEVEN", "PROFIT_LOCK"]:
            consensus_factors.append(("psl_advanced", 0.7))
            
        # Factor 3: Significant profit drawdown
        if max_profit_seen > 0 and current_pnl < max_profit_seen * 0.7:
            consensus_factors.append(("profit_drawdown", 0.6))
            
        # Calculate weighted consensus
        if consensus_factors:
            total_weight = sum(f[1] for f in consensus_factors)
            avg_confidence = total_weight / len(consensus_factors)
            
            if avg_confidence >= 0.6:  # Consensus threshold
                reasons = ", ".join([f[0] for f in consensus_factors])
                return ExitDecision(
                    should_exit=True,
                    decision_type=ExitDecisionType.HYBRID_CONSENSUS,
                    confidence=avg_confidence,
                    reason=f"Consensus exit: {reasons}"
                )
                
        return None
        
    def _track_decision(
        self,
        decision: ExitDecision,
        timestamp: datetime,
        current_pnl: float
    ):
        """Track decision for analysis and learning"""
        self.decision_history.append({
            "timestamp": timestamp,
            "decision": decision,
            "pnl_at_decision": current_pnl
        })
        
    def update_accuracy(
        self,
        decision_type: ExitDecisionType,
        was_correct: bool
    ):
        """
        Update accuracy tracking for ML vs rule-based decisions
        
        Args:
            decision_type: Type of decision that was made
            was_correct: Whether the decision was profitable
        """
        if decision_type == ExitDecisionType.ML_PREDICTED:
            if was_correct:
                self.ml_accuracy_tracker["correct"] += 1
            else:
                self.ml_accuracy_tracker["incorrect"] += 1
        elif decision_type == ExitDecisionType.PROGRESSIVE_SL:
            if was_correct:
                self.rule_accuracy_tracker["correct"] += 1
            else:
                self.rule_accuracy_tracker["incorrect"] += 1
                
    def get_performance_stats(self) -> Dict:
        """Get performance statistics for ML vs rule-based decisions"""
        ml_total = sum(self.ml_accuracy_tracker.values())
        rule_total = sum(self.rule_accuracy_tracker.values())
        
        return {
            "ml_accuracy": (
                self.ml_accuracy_tracker["correct"] / ml_total * 100
                if ml_total > 0 else 0
            ),
            "rule_accuracy": (
                self.rule_accuracy_tracker["correct"] / rule_total * 100
                if rule_total > 0 else 0
            ),
            "ml_decisions": ml_total,
            "rule_decisions": rule_total,
            "total_decisions": len(self.decision_history)
        }
        
    def optimize_thresholds(
        self,
        historical_decisions: List[Dict]
    ) -> Dict:
        """
        Optimize ML confidence threshold based on historical performance
        
        Args:
            historical_decisions: Past decisions with outcomes
            
        Returns:
            Optimized thresholds
        """
        best_threshold = self.ml_confidence_threshold
        best_accuracy = 0
        
        # Test different thresholds
        for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
            correct = 0
            total = 0
            
            for decision in historical_decisions:
                if decision["ml_confidence"] >= threshold:
                    total += 1
                    if decision["was_profitable"]:
                        correct += 1
                        
            if total > 0:
                accuracy = correct / total
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_threshold = threshold
                    
        return {
            "optimal_ml_threshold": best_threshold,
            "expected_accuracy": best_accuracy * 100
        }