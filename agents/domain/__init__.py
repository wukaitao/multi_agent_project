"""领域专家 Agent """

from .coding.agent import CodingAgent
from .medical.agent import MedicalAgent
from .entertainment.agent import EntertainmentAgent
from .finance.agent import FinanceAgent
from .office.agent import OfficeAgent

__all__ = [
    "CodingAgent",
    "MedicalAgent",
    "EntertainmentAgent",
    "FinanceAgent",
    "OfficeAgent"
]