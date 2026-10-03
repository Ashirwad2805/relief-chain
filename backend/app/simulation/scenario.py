import random
import math
from app.adapters.mumbai_geo import MUMBAI_AREAS

def generate_mumbai_scenario(seed: int = 42) -> dict:
    """
    Generates a rich, deterministic Mumbai Monsoon Surge scenario:
    - 18 Hospitals with specialty profiles & blood stocks
    - 40 Ambulances (basic, advanced, icu, boat, helicopter)
    - 8 Casualty clusters across flood-affected zones
    - 4 Supply depots / warehouses
    - 10 Road arteries with dynamic conditions
    - Emergency funds & relief allocations
    """
    rng = random.Random(seed)

    # 1. 18 Hospitals
    # E2 fix: Hospital areas verified against public OpenStreetMap data.
    # KEM is in Parel (not Sion); Cooper is in Vile Parle W (not Bandra);
    # Hinduja is in Mahim (not Worli); Fortis Mulund is in Mulund (not Kurla).
    # All hospital coordinates use MUMBAI_AREAS[area] + small RNG jitter so
    # individual buildings within the locality differ slightly.
    hospital_defs = [
        ("H01", "KEM Hospital",                     "Parel",      ["trauma", "cardiac", "pediatric"],   45, 22, 120),
        ("H02", "Lokmanya Tilak Municipal (Sion)",   "Sion",       ["trauma", "neuro"],                  40, 18, 100),
        ("H03", "Holy Spirit Hospital",              "Andheri",    ["cardiac", "general"],               30, 14,  75),
        ("H04", "Cooper Hospital",                   "Vile Parle", ["trauma", "pediatric"],              35, 16,  85),
        ("H05", "P.D. Hinduja Hospital",             "Mahim",      ["neuro", "cardiac", "trauma"],       35, 20,  95),
        ("H06", "Breach Candy Hospital",             "Worli",      ["general", "cardiac"],               25, 12,  60),
        ("H07", "Nanavati Max Hospital",             "Juhu",       ["trauma", "general", "pediatric"],   32, 15,  70),
        ("H08", "Fortis Hospital Mulund",            "Mulund",     ["cardiac", "neuro"],                 28, 14,  65),
        ("H09", "Tata Memorial Hospital",            "Parel",      ["oncology", "general"],              30, 12,  80),
        ("H10", "Bhatia Hospital",                   "Byculla",    ["general", "trauma"],                24, 10,  50),
        ("H11", "Surana Sethia Hospital",            "Chembur",    ["cardiac", "general"],               26, 12,  55),
        ("H12", "Godrej Memorial Hospital",          "Ghatkopar",  ["trauma", "cardiac"],                28, 12,  60),
        ("H13", "Kokilaben Dhirubhai Ambani",        "Andheri",    ["trauma", "neuro", "pediatric"],     40, 24, 110),
        ("H14", "Lilavati Hospital",                 "Bandra",     ["cardiac", "neuro", "trauma"],       38, 20,  90),
        ("H15", "Saifee Hospital",                   "Byculla",    ["general", "cardiac"],               30, 14,  70),
        ("H16", "Jaslok Hospital",                   "Worli",      ["neuro", "cardiac"],                 32, 16,  80),
        ("H17", "HBT Trauma Care Hospital",          "Vile Parle", ["trauma", "ortho"],                  30, 12,  60),
        ("H18", "St. George Hospital",               "Colaba",     ["general", "trauma"],                25, 10,  50),
    ]

    hospitals = []
    for hid, name, area, specs, er_cap, icu_cap, ward_cap in hospital_defs:
        pos = MUMBAI_AREAS.get(area, {"lat": 19.05, "lng": 72.84})
        hospitals.append({
            "id": hid,
            "name": name,
            "area": area,
            "specialty": specs,
            "capacity": {"er": er_cap, "icu": icu_cap, "ward": ward_cap},
            "occupied": {
                "er": rng.randint(int(er_cap * 0.4), int(er_cap * 0.85)),
                "icu": rng.randint(int(icu_cap * 0.3), int(icu_cap * 0.8)),
                "ward": rng.randint(int(ward_cap * 0.5), int(ward_cap * 0.9))
            },
            "blood": {
                "A+": rng.randint(8, 25), "A-": rng.randint(3, 12),
                "B+": rng.randint(8, 25), "B-": rng.randint(2, 10),
                "O+": rng.randint(12, 35), "O-": rng.randint(4, 18),
                "AB+": rng.randint(3, 10), "AB-": rng.randint(1, 6)
            },
            "status": "operational",
            "position": {"lat": pos["lat"] + (rng.random() - 0.5) * 0.008, "lng": pos["lng"] + (rng.random() - 0.5) * 0.008}
        })

    # 2. 40 Ambulances
    types = ["basic", "advanced", "icu", "boat", "helicopter"]
    type_weights = [18, 12, 6, 3, 1]
    expanded_types = []
    for t, count in zip(types, type_weights):
        expanded_types.extend([t] * count)

    ambulances = []
    for i in range(1, 41):
        amb_id = f"AMB-{str(i).padStart(2, '0')}" if False else f"AMB-{str(i).zfill(2)}"
        amb_type = expanded_types[i - 1]
        home_hosp = hospitals[rng.randint(0, len(hospitals) - 1)]
        cap_val = 4 if amb_type == "helicopter" else 3 if amb_type == "icu" else 2 if amb_type in ("advanced", "boat") else 1
        pos = home_hosp["position"]
        # Position idle fleet directly at home hospital base station (neat 40-60m station offset)
        offset_angle = (i * 1.25) % (2 * math.pi)
        ambulances.append({
            "id": amb_id,
            "type": amb_type,
            "status": "idle",
            "position": {
                "lat": pos["lat"] + 0.0006 * math.cos(offset_angle),
                "lng": pos["lng"] + 0.0006 * math.sin(offset_angle)
            },
            "assignedIncidentId": None,
            "assignedHospitalId": None,
            "fuel": rng.randint(70, 100),
            "homeHospital": home_hosp["id"],
            "capability": cap_val
        })

    # 3. 8 Casualty Clusters
    incident_defs = [
        ("INC-001", "Building Collapse – Dadar Kabutar Khana", "Dadar", "red", 18, 14, 22, "3-storey residential collapse; multiple victims trapped under masonry"),
        ("INC-002", "Severe Flooding – Hindmata Junction", "Hindmata", "red", 14, 28, 45, "Monsoon storm surge over 4.5ft; stranded buses and electric shock hazards"),
        ("INC-003", "Andheri Subway Flash Submersion", "Andheri", "yellow", 6, 18, 30, "Subway inundated rapidly; submerged public transport vehicles"),
        ("INC-004", "Milan Subway Waterlogging & Gridlock", "Milan Subway", "yellow", 4, 12, 18, "Major arterial gridlock with elderly and asthmatic patients stranded"),
        ("INC-005", "Sion Circle Inundation & Debris", "Sion Circle", "yellow", 5, 10, 25, "Key traffic rotunda flooded; ambulance transit blocked"),
        ("INC-006", "Kurla Low-lying Shanty Inundation", "Kurla", "red", 12, 22, 35, "Mithi river overflow entering residential settlements; water-borne trauma"),
        ("INC-007", "Bandra Station West Overpass Rush", "Bandra", "yellow", 3, 14, 20, "Crush injury event following unexpected commuter evacuation"),
        ("INC-008", "Worli Sea Face Coastal Inundation", "Worli", "green", 1, 6, 15, "High-tide wave overtopping promenade; minor lacerations and trauma")
    ]

    incidents = []
    for inc_id, label, area, sev, red, yel, grn, desc in incident_defs:
        pos = MUMBAI_AREAS.get(area, {"lat": 19.05, "lng": 72.84})
        incidents.append({
            "id": inc_id,
            "label": label,
            "severity": sev,
            "area": area,
            "position": {"lat": pos["lat"] + (rng.random() - 0.5) * 0.006, "lng": pos["lng"] + (rng.random() - 0.5) * 0.006},
            "patientCount": red + yel + grn,
            "redPatients": red,
            "yellowPatients": yel,
            "greenPatients": grn,
            "bloodNeeded": ["O-", "B+"] if sev == "red" else ["O+"],
            "urgency": rng.randint(85, 98) if sev == "red" else rng.randint(45, 70),
            "slaMinutes": 15 if sev == "red" else 30,
            "createdAt": round(rng.uniform(0.5, 3.0), 1),
            "status": "active",
            "description": desc,
            "assignedAmbulanceId": None,
            "assignedHospitalId": None,
            "etaMinutes": None
        })

    # 4. Roads with Conditions
    road_defs = [
        ("Andheri", "Sion", "slow"),
        ("Sion", "Dadar", "open"),
        ("Dadar", "Hindmata", "flooded"),
        ("Hindmata", "Sion Circle", "flooded"),
        ("Sion Circle", "Sion", "slow"),
        ("Milan Subway", "Andheri", "flooded"),
        ("Bandra", "Sion", "open"),
        ("Andheri", "Juhu", "open"),
        ("Worli", "Dadar", "open"),
        ("Kurla", "Sion", "slow"),
        ("Parel", "Dadar", "open"),
        ("Byculla", "Parel", "open"),
        ("Chembur", "Kurla", "slow"),
        ("Ghatkopar", "Kurla", "open")
    ]

    roads = []
    for i, (u, v, cond) in enumerate(road_defs, start=1):
        roads.append({
            "id": f"R{i}",
            "from": u,
            "to": v,
            "condition": cond,
            "fromPos": MUMBAI_AREAS[u],
            "toPos": MUMBAI_AREAS[v]
        })

    # 5. Supplies & Logistics
    supplies = [
        {"id": "SUP-001", "name": "Emergency IV Fluids (Ringer Lactate)", "type": "medical", "quantity": 1200, "unit": "units", "location": "KEM Central Depot", "status": "available"},
        {"id": "SUP-002", "name": "Sterile Trauma Bandages & Dressing", "type": "medical", "quantity": 4000, "unit": "rolls", "location": "Hinduja Depot", "status": "available"},
        {"id": "SUP-003", "name": "High-Pressure Medical Oxygen Cylinders", "type": "medical", "quantity": 150, "unit": "cylinders", "location": "Kurla Central Logistics", "status": "available"},
        {"id": "SUP-004", "name": "Anti-Tetanus Immunoglobulin & Toxoid", "type": "medical", "quantity": 800, "unit": "vials", "location": "Nanavati Store", "status": "available"},
        {"id": "SUP-005", "name": "Potable Drinking Water Pouches (500ml)", "type": "water", "quantity": 10000, "unit": "pouches", "location": "Bandra Relief Camp", "status": "available"},
        {"id": "SUP-006", "name": "MRE Nutrient Rations", "type": "food", "quantity": 6000, "unit": "packets", "location": "Dadar Red Cross", "status": "available"},
        {"id": "SUP-007", "name": "Heavy-Duty Tarpaulin Rain Covers", "type": "shelter", "quantity": 500, "unit": "sheets", "location": "Sion Civic Hall", "status": "available"},
        {"id": "SUP-008", "name": "Generator Diesel (Ultra-Low Sulfur)", "type": "fuel", "quantity": 2500, "unit": "liters", "location": "BPCL Kurla Depot", "status": "available"}
    ]

    supply_requests = [
        {"id": "REQ-001", "item": "High-Pressure Medical Oxygen Cylinders", "quantity": 25, "unit": "cylinders", "requester": "Lokmanya Tilak (Sion)", "area": "Sion", "priority": "urgent", "status": "pending", "createdAt": 1.2},
        {"id": "REQ-002", "item": "Emergency IV Fluids (Ringer Lactate)", "quantity": 300, "unit": "units", "requester": "Cooper Hospital", "area": "Bandra", "priority": "high", "status": "pending", "createdAt": 2.0},
        {"id": "REQ-003", "item": "Potable Drinking Water Pouches (500ml)", "quantity": 1200, "unit": "pouches", "requester": "Hindmata Rescue Shelter", "area": "Hindmata", "priority": "urgent", "status": "pending", "createdAt": 2.5},
        {"id": "REQ-004", "item": "Anti-Tetanus Immunoglobulin & Toxoid", "quantity": 100, "unit": "vials", "requester": "Dadar Community Clinic", "area": "Dadar", "priority": "normal", "status": "pending", "createdAt": 3.1}
    ]

    # 6. Funds
    funds = [
        {"id": "F1", "donor": "Maharashtra State Disaster Management Authority", "amount": 100000000.0, "purpose": "Emergency Operations Pool", "stage": "released", "recipient": "Emergency Pool", "timestamp": 0.5},
        {"id": "F2", "donor": "Mumbai Business Relief Council", "amount": 50000000.0, "purpose": "Trauma Medicine & Oxygen Logistics", "stage": "allocated", "recipient": "Logistics Command", "timestamp": 1.0},
        {"id": "F3", "donor": "Tata Trust Humanitarian Relief", "amount": 25000000.0, "purpose": "Flood Zone Rescue Boat Deployment", "stage": "pledged", "recipient": "Water Rescue Fleet", "timestamp": 2.2}
    ]

    return {
        "hospitals": hospitals,
        "ambulances": ambulances,
        "incidents": incidents,
        "roads": roads,
        "supplies": supplies,
        "supplyRequests": supply_requests,
        "funds": funds
    }
