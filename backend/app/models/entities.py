import json
from sqlalchemy import Column, Integer, Float, String, Boolean, Text, ForeignKey, JSON
from app.database import Base

class HospitalModel(Base):
    __tablename__ = "hospitals"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    area = Column(String(100), nullable=False)
    specialty = Column(JSON, default=list)
    capacity_er = Column(Integer, default=30)
    capacity_icu = Column(Integer, default=15)
    capacity_ward = Column(Integer, default=80)
    occupied_er = Column(Integer, default=0)
    occupied_icu = Column(Integer, default=0)
    occupied_ward = Column(Integer, default=0)
    blood_json = Column(JSON, default=dict)
    status = Column(String(50), default="operational")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty or [],
            "capacity": {
                "er": self.capacity_er,
                "icu": self.capacity_icu,
                "ward": self.capacity_ward
            },
            "occupied": {
                "er": self.occupied_er,
                "icu": self.occupied_icu,
                "ward": self.occupied_ward
            },
            "blood": self.blood_json or {},
            "status": self.status,
            "position": {"lat": self.lat, "lng": self.lng},
            "area": self.area
        }

class AmbulanceModel(Base):
    __tablename__ = "ambulances"

    id = Column(String(50), primary_key=True, index=True)
    type = Column(String(50), default="basic")
    status = Column(String(50), default="idle")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    assigned_incident_id = Column(String(50), nullable=True)
    assigned_hospital_id = Column(String(50), nullable=True)
    fuel = Column(Integer, default=100)
    home_hospital = Column(String(50), default="H1")
    capability = Column(Integer, default=1)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "position": {"lat": self.lat, "lng": self.lng},
            "assignedIncidentId": self.assigned_incident_id,
            "assignedHospitalId": self.assigned_hospital_id,
            "fuel": self.fuel,
            "homeHospital": self.home_hospital,
            "capability": self.capability
        }

class IncidentModel(Base):
    __tablename__ = "incidents"

    id = Column(String(50), primary_key=True, index=True)
    label = Column(String(200), nullable=False)
    severity = Column(String(50), default="yellow")
    area = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    patient_count = Column(Integer, default=10)
    red_patients = Column(Integer, default=2)
    yellow_patients = Column(Integer, default=5)
    green_patients = Column(Integer, default=3)
    blood_needed = Column(JSON, default=list)
    urgency = Column(Integer, default=50)
    sla_minutes = Column(Integer, default=30)
    created_at = Column(Float, default=0.0)
    status = Column(String(50), default="active")
    description = Column(Text, default="")
    assigned_ambulance_id = Column(String(50), nullable=True)
    assigned_hospital_id = Column(String(50), nullable=True)
    eta_minutes = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "severity": self.severity,
            "area": self.area,
            "position": {"lat": self.lat, "lng": self.lng},
            "patientCount": self.patient_count,
            "redPatients": self.red_patients,
            "yellowPatients": self.yellow_patients,
            "greenPatients": self.green_patients,
            "bloodNeeded": self.blood_needed or [],
            "urgency": self.urgency,
            "slaMinutes": self.sla_minutes,
            "createdAt": self.created_at,
            "status": self.status,
            "description": self.description,
            "assignedAmbulanceId": self.assigned_ambulance_id,
            "assignedHospitalId": self.assigned_hospital_id,
            "etaMinutes": self.eta_minutes
        }

class RoadModel(Base):
    __tablename__ = "roads"

    id = Column(String(50), primary_key=True, index=True)
    from_area = Column(String(100), nullable=False)
    to_area = Column(String(100), nullable=False)
    condition = Column(String(50), default="open")
    from_lat = Column(Float, nullable=False)
    from_lng = Column(Float, nullable=False)
    to_lat = Column(Float, nullable=False)
    to_lng = Column(Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "from": self.from_area,
            "to": self.to_area,
            "condition": self.condition,
            "fromPos": {"lat": self.from_lat, "lng": self.from_lng},
            "toPos": {"lat": self.to_lat, "lng": self.to_lng}
        }

class SupplyItemModel(Base):
    __tablename__ = "supplies"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), default="medical")
    quantity = Column(Integer, default=0)
    unit = Column(String(50), default="units")
    location = Column(String(100), default="Warehouse")
    status = Column(String(50), default="available")
    destination = Column(String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "quantity": self.quantity,
            "unit": self.unit,
            "location": self.location,
            "status": self.status,
            "destination": self.destination
        }

class SupplyRequestModel(Base):
    __tablename__ = "supply_requests"

    id = Column(String(50), primary_key=True, index=True)
    item = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    unit = Column(String(50), default="units")
    requester = Column(String(100), nullable=False)
    area = Column(String(100), nullable=False)
    priority = Column(String(50), default="normal")
    status = Column(String(50), default="pending")
    created_at = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "item": self.item,
            "quantity": self.quantity,
            "unit": self.unit,
            "requester": self.requester,
            "area": self.area,
            "priority": self.priority,
            "status": self.status,
            "createdAt": self.created_at
        }

class DecisionModel(Base):
    __tablename__ = "decisions"

    id = Column(String(100), primary_key=True, index=True)
    timestamp = Column(Float, default=0.0)
    incident_id = Column(String(50), nullable=False)
    incident_label = Column(String(200), nullable=False)
    ambulance_id = Column(String(50), nullable=False)
    hospital_id = Column(String(50), nullable=False)
    selected_hospital_name = Column(String(100), nullable=False)
    nearest_hospital_id = Column(String(50), nullable=False)
    nearest_hospital_name = Column(String(100), nullable=False)
    action = Column(String(200), default="")
    score = Column(Float, default=0.0)
    alternatives = Column(JSON, default=list)
    constraints = Column(JSON, default=list)
    explanation = Column(JSON, default=dict)
    status = Column(String(50), default="suggested")
    override_reason = Column(Text, nullable=True)
    pinned = Column(Boolean, default=False)
    engine = Column(String(50), default="reliefchain")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "incidentId": self.incident_id,
            "incidentLabel": self.incident_label,
            "ambulanceId": self.ambulance_id,
            "hospitalId": self.hospital_id,
            "selectedHospitalName": self.selected_hospital_name,
            "nearestHospitalId": self.nearest_hospital_id,
            "nearestHospitalName": self.nearest_hospital_name,
            "action": self.action,
            "score": self.score,
            "alternatives": self.alternatives or [],
            "constraints": self.constraints or [],
            "explanation": self.explanation or {},
            "status": self.status,
            "overrideReason": self.override_reason,
            "pinned": self.pinned,
            "engine": self.engine
        }

class LedgerBlockModel(Base):
    __tablename__ = "ledger_blocks"

    index = Column(Integer, primary_key=True, index=True)
    timestamp = Column(Float, default=0.0)
    previous_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False)
    merkle_root = Column(String(64), nullable=False)
    entries = Column(JSON, default=list)
    verified = Column(Boolean, default=True)
    tampered = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "previousHash": self.previous_hash,
            "hash": self.hash,
            "merkleRoot": self.merkle_root,
            "entries": self.entries or [],
            "verified": self.verified,
            "tampered": self.tampered
        }

class FundFlowModel(Base):
    __tablename__ = "funds"

    id = Column(String(50), primary_key=True, index=True)
    donor = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    purpose = Column(String(200), default="Disaster Relief")
    stage = Column(String(50), default="pledged")
    recipient = Column(String(100), default="Emergency Pool")
    timestamp = Column(Float, default=0.0)
    delivery_amount = Column(Float, nullable=True)
    delivery_unit = Column(String(50), nullable=True)
    delivery_qty = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "donor": self.donor,
            "amount": self.amount,
            "purpose": self.purpose,
            "stage": self.stage,
            "recipient": self.recipient,
            "timestamp": self.timestamp,
            "deliveryAmount": self.delivery_amount,
            "deliveryUnit": self.delivery_unit,
            "deliveryQty": self.delivery_qty
        }

class AnomalyModel(Base):
    __tablename__ = "anomalies"

    id = Column(String(50), primary_key=True, index=True)
    type = Column(String(50), nullable=False)
    severity = Column(String(50), default="medium")
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    evidence = Column(JSON, default=list)
    linked_records = Column(JSON, default=list)
    status = Column(String(50), default="new")
    notes = Column(Text, default="")
    detected_at = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence or [],
            "linkedRecords": self.linked_records or [],
            "status": self.status,
            "notes": self.notes,
            "detectedAt": self.detected_at
        }

class SimEventModel(Base):
    __tablename__ = "sim_events"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(Float, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    type = Column(String(50), default="general")
    triggered = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "time": self.time,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "triggered": self.triggered
        }

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False)
    user = Column(String(100), default="Operator")
    role = Column(String(50), default="Control Room")
    action = Column(String(100), nullable=False)
    details = Column(JSON, default=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "user": self.user,
            "role": self.role,
            "action": self.action,
            "details": self.details or {}
        }
