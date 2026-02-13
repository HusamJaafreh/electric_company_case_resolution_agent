#core/case_resolution/schema.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class CaseResolutionState:
    incoming_text: str = ""
    phone: Optional[str] = None
    account_id: Optional[str] = None
    case_id: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    decision: Optional[str] = None
    reply_text: Optional[str] = None
