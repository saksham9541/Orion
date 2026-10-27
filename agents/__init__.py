"""
Orion — Multi-Agent Railway Maintenance Optimization System.

Specialized autonomous agents:
- DepartmentAgent: Engineering, S&T, and TRD domain representatives
- ArbitratorAgent: Cross-department conflict resolution and block merging
- EarlyWarningAgent: Predictive defect clustering and seasonal risk monitoring
- ReplanningAgent: Dynamic mid-cycle emergency schedule repair
- AgentOrchestrator: Collaborative negotiation and consensus planner
"""
from .department_agent import DepartmentAgent, DepartmentProposal
from .arbitrator_agent import ArbitratorAgent, NegotiationAgreement, ConflictResolution
from .early_warning_agent import EarlyWarningAgent
from .replanning_agent import ReplanningAgent
from .agent_orchestrator import AgentOrchestrator, AgentConsensusPlan

__all__ = [
    "DepartmentAgent",
    "DepartmentProposal",
    "ArbitratorAgent",
    "NegotiationAgreement",
    "ConflictResolution",
    "EarlyWarningAgent",
    "ReplanningAgent",
    "AgentOrchestrator",
    "AgentConsensusPlan",
]
