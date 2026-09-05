from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from schemas_v2 import RawJobPayload, JobListing, CandidateFitEvaluation


@dataclass
class AgentExecutionState:
    """Drží stav multi-agentního běhu (Saga pattern s failoverem a částečnými výsledky)."""
    run_id: str
    query: str
    market: str  # "cz", "global", "hybrid"
    requested_count: int
    raw_payloads: List[RawJobPayload] = field(default_factory=list)
    normalized_listings: List[JobListing] = field(default_factory=list)
    scored_listings: List[Dict[str, Any]] = field(default_factory=list)
    worker_errors: Dict[str, str] = field(default_factory=dict)
    worker_counts: Dict[str, int] = field(default_factory=dict)
    status: str = "INITIALIZED"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_worker_success(self, worker_name: str, count: int):
        self.worker_counts[worker_name] = count

    def record_worker_failure(self, worker_name: str, error: Exception):
        self.worker_errors[worker_name] = str(error)
