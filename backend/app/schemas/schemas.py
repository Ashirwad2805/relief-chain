from pydantic import BaseModel, Field
from typing import Literal, Any

Role = Literal['Judge', 'Control Room', 'Hospital', 'NGO', 'Donor', 'Auditor', 'Public']
Severity = Literal['red', 'yellow', 'green']
IncidentStatus = Literal['active', 'assigned', 'transporting', 'admitted', 'resolved']
AmbulanceStatus = Literal['idle', 'dispatched', 'transporting', 'returning', 'broken']
AmbulanceType = Literal['basic', 'advanced', 'icu', 'boat']
HospitalStatus = Literal['operational', 'overloaded', 'power_failure', 'full']
RoadCondition = Literal['open', 'flooded', 'blocked', 'slow']
DecisionStatus = Literal['suggested', 'approved', 'auto_applied', 'overridden', 'stale']
AnomalyStatus = Literal['new', 'investigating', 'resolved', 'escalated']
AnomalySeverity = Literal['low', 'medium', 'high', 'critical']

class GeoPoint(BaseModel):
    lat: float
    lng: float

class HospitalCapacity(BaseModel):
    er: int
    icu: int
    ward: int

class HospitalSchema(BaseModel):
    id: str
    name: str
    specialty: list[str] = Field(default_factory=list)
    capacity: HospitalCapacity
    occupied: HospitalCapacity
    blood: dict[str, int] = Field(default_factory=dict)
    status: HospitalStatus
    position: GeoPoint
    area: str

class AmbulanceSchema(BaseModel):
    id: str
    type: AmbulanceType
    status: AmbulanceStatus
    position: GeoPoint
    assignedIncidentId: str | None = None
    assignedHospitalId: str | None = None
    fuel: int = 100
    homeHospital: str = "H1"
    capability: int = 1

class IncidentSchema(BaseModel):
    id: str
    label: str
    severity: Severity
    area: str
    position: GeoPoint
    patientCount: int
    redPatients: int
    yellowPatients: int
    greenPatients: int
    bloodNeeded: list[str] = Field(default_factory=list)
    urgency: int
    slaMinutes: int
    createdAt: float
    status: IncidentStatus
    description: str
    assignedAmbulanceId: str | None = None
    assignedHospitalId: str | None = None
    etaMinutes: float | None = None

class RoadSchema(BaseModel):
    id: str
    from_: str = Field(alias="from")
    to: str
    condition: RoadCondition
    fromPos: GeoPoint
    toPos: GeoPoint

    class Config:
        populate_by_name = True

class SupplyItemSchema(BaseModel):
    id: str
    name: str
    type: Literal['medical', 'food', 'water', 'shelter', 'fuel']
    quantity: int
    unit: str
    location: str
    status: Literal['available', 'in_transit', 'delivered', 'stuck']
    destination: str | None = None

class SupplyRequestSchema(BaseModel):
    id: str
    item: str
    quantity: int
    unit: str
    requester: str
    area: str
    priority: Literal['urgent', 'high', 'normal']
    status: Literal['pending', 'allocated', 'dispatched', 'delivered']
    createdAt: float

class HospitalAlternativeSchema(BaseModel):
    hospitalId: str
    hospitalName: str
    score: float
    distance: float
    etaMinutes: float
    accepted: bool
    reasons: list[str]

class DecisionExplanationSchema(BaseModel):
    selectedReasons: list[str]
    nearestRejectedReasons: list[str]
    expectedSurvivors: int
    baselineSurvivors: int

class AllocationDecisionSchema(BaseModel):
    id: str
    timestamp: float
    incidentId: str
    incidentLabel: str
    ambulanceId: str
    hospitalId: str
    selectedHospitalName: str
    nearestHospitalId: str
    nearestHospitalName: str
    action: str
    score: float
    alternatives: list[HospitalAlternativeSchema] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    explanation: DecisionExplanationSchema
    status: DecisionStatus
    overrideReason: str | None = None
    pinned: bool = False
    engine: Literal['reliefchain', 'baseline'] = 'reliefchain'

class LedgerEntrySchema(BaseModel):
    type: Literal['allocation', 'dispatch', 'pickup', 'admission', 'supply_transfer', 'fund_pledge', 'fund_release', 'vendor_payment', 'delivery_confirmation', 'override']
    description: str
    amount: float | None = None
    entityId: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class LedgerBlockSchema(BaseModel):
    index: int
    timestamp: float
    previousHash: str
    hash: str
    merkleRoot: str
    entries: list[LedgerEntrySchema]
    verified: bool = True
    tampered: bool = False

class FundFlowSchema(BaseModel):
    id: str
    donor: str
    amount: float
    purpose: str
    stage: Literal['pledged', 'allocated', 'released', 'delivered', 'verified']
    recipient: str
    timestamp: float
    deliveryAmount: float | None = None
    deliveryUnit: str | None = None
    deliveryQty: float | None = None

class AnomalySchema(BaseModel):
    id: str
    type: Literal['duplicate_claim', 'duplicate_beneficiary', 'over_allocation', 'unusual_pricing', 'ghost_delivery']
    severity: AnomalySeverity
    title: str
    description: str
    evidence: list[str]
    linkedRecords: list[str]
    status: AnomalyStatus
    notes: str = ""
    detectedAt: float

class SimEventSchema(BaseModel):
    id: int
    time: float
    title: str
    description: str
    type: str
    triggered: bool = False

class SimStatsSchema(BaseModel):
    estimatedSurvivors: int
    baselineSurvivors: int
    avgRedTreatmentTime: int
    worstTreatmentTime: int
    icuOverloads: int
    unservedCritical: int
    ambulanceUtilization: int
    equityScore: int
    pendingDecisions: int
    activeAmbulances: int
    activeIncidents: int
    hospitalOverloads: int
    activeSupplyRequests: int
    bloodAvailability: int
    icuAvailability: int

class WorldStateSchema(BaseModel):
    simTime: float
    startTime: float
    running: bool
    speed: float
    hospitals: list[HospitalSchema]
    ambulances: list[AmbulanceSchema]
    incidents: list[IncidentSchema]
    roads: list[RoadSchema]
    supplies: list[SupplyItemSchema]
    supplyRequests: list[SupplyRequestSchema]
    decisions: list[AllocationDecisionSchema]
    events: list[SimEventSchema]
    ledger: list[LedgerBlockSchema]
    funds: list[FundFlowSchema]
    anomalies: list[AnomalySchema]
    stats: SimStatsSchema
    alert: str | None = None
    autopilotActive: bool = False
    autopilotStep: int = 0

class ChaosRequest(BaseModel):
    action: str

class OverrideRequest(BaseModel):
    id: str
    reason: str
    newHospitalId: str
    user: str = "Operator"

class ApprovalRequest(BaseModel):
    id: str
    user: str = "Operator"

class TamperRequest(BaseModel):
    blockIndex: int

class MerkleProofResponse(BaseModel):
    leafHash: str
    merkleRoot: str
    blockIndex: int
    proofPath: list[dict[str, str]]
    valid: bool
