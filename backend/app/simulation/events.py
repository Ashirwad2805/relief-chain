from typing import Any

def get_simulation_events() -> list[dict]:
    """Returns the 15 core deterministic simulation events for the Mumbai scenario."""
    return [
        {
            "id": 1,
            "time": 1.0,
            "title": "Initial Flooding Across Low-Lying Arteries",
            "description": "Heavy monsoon downpour (120mm/hr) causes flash waterlogging in Hindmata, Milan Subway, and Sion Circle.",
            "type": "flood",
            "triggered": False
        },
        {
            "id": 2,
            "time": 2.0,
            "title": "Building Collapse – Dadar Kabutar Khana",
            "description": "3-storey dilapidated structure collapses under heavy rainfall. 18 critical casualties reported.",
            "type": "collapse",
            "triggered": False
        },
        {
            "id": 3,
            "time": 3.5,
            "title": "Critical Casualty Cluster Reported",
            "description": "Surge of crush and polytrauma victims identified at Hindmata requiring urgent ICU admission.",
            "type": "casualty",
            "triggered": False
        },
        {
            "id": 4,
            "time": 4.5,
            "title": "Andheri Subway Flooding (4.5ft Water)",
            "description": "Subway completely inundated. Vehicles submerged; east-west connectivity severed.",
            "type": "flood",
            "triggered": False
        },
        {
            "id": 5,
            "time": 5.5,
            "title": "Hospital ICU Capacity Reduction",
            "description": "Lokmanya Tilak (Sion) ICU reaches 100% capacity. Diverting all incoming critical ambulances.",
            "type": "capacity",
            "triggered": False
        },
        {
            "id": 6,
            "time": 6.5,
            "title": "O-Negative Blood Shortage",
            "description": "City-wide reserves of O-negative blood fall to critical levels (<4 units in central banks).",
            "type": "blood",
            "triggered": False
        },
        {
            "id": 7,
            "time": 7.5,
            "title": "Ambulance Breakdown in Flooded Zone",
            "description": "AMB-04 encounters engine hydrostatic lock near Sion Circle. Mission reassignment required.",
            "type": "ambulance",
            "triggered": False
        },
        {
            "id": 8,
            "time": 8.5,
            "title": "Flood-Zone Casualty Cluster (Hindmata Deep Zone)",
            "description": "Water rescue boat required for 20 stranded residents with hypothermia and trauma.",
            "type": "casualty",
            "triggered": False
        },
        {
            "id": 9,
            "time": 9.5,
            "title": "Bridge Closure (Sion-Dadar Flyover)",
            "description": "Structural joint displacement observed on flyover; police barricade bridge completely.",
            "type": "road",
            "triggered": False
        },
        {
            "id": 10,
            "time": 10.5,
            "title": "Hospital Power Failure (Cooper Hospital)",
            "description": "Cooper Hospital loses grid power; backup generator operating at 50% capacity.",
            "type": "power",
            "triggered": False
        },
        {
            "id": 11,
            "time": 11.5,
            "title": "Paediatric Surge at Kurla Settlement",
            "description": "15 paediatric cases needing urgent specialized pediatric trauma and respiratory support.",
            "type": "surge",
            "triggered": False
        },
        {
            "id": 12,
            "time": 12.5,
            "title": "Donor Funds Arrival (₹50,000,000 Released)",
            "description": "Emergency funds released to logistics pool for fuel, oxygen, and emergency medical replenishment.",
            "type": "funds",
            "triggered": False
        },
        {
            "id": 13,
            "time": 13.5,
            "title": "Supply Vehicle Stuck in Mud / Water",
            "description": "Truck carrying 40 oxygen cylinders trapped in Kurla junction; requires escort or boat transfer.",
            "type": "supply",
            "triggered": False
        },
        {
            "id": 14,
            "time": 14.2,
            "title": "Duplicate Beneficiary Claim Detected",
            "description": "Automated ledger integrity scan detects identical token claim at Dadar and Hindmata relief camps.",
            "type": "anomaly",
            "triggered": False
        },
        {
            "id": 15,
            "time": 15.0,
            "title": "Road Reopening (Bandra-Sion Cleared)",
            "description": "Pumping stations clear Bandra-Sion corridor. Normal high-speed transit restored.",
            "type": "road",
            "triggered": False
        }
    ]

def apply_event_mutation(event: dict, state: dict) -> dict:
    """Modifies the state according to the event specification."""
    e_type = event.get("type")
    e_id = event.get("id")

    hospitals = state["hospitals"]
    ambulances = state["ambulances"]
    incidents = state["incidents"]
    roads = state["roads"]
    supplies = state["supplies"]
    funds = state["funds"]

    alert = f"EVENT TRIGGERED: {event['title']}"

    if e_type == "flood":
        if "Andheri" in event["title"]:
            for r in roads:
                if r.get("from") == "Andheri" or r.get("to") == "Andheri":
                    r["condition"] = "flooded"
        else:
            for r in roads:
                if r.get("from") in ("Hindmata", "Milan Subway", "Sion Circle"):
                    r["condition"] = "flooded"

    elif e_type == "collapse":
        dadar_inc = next((i for i in incidents if i.get("area") == "Dadar"), None)
        if dadar_inc:
            dadar_inc["redPatients"] += 8
            dadar_inc["patientCount"] += 12
            dadar_inc["urgency"] = 99

    elif e_type == "capacity":
        sion_h = next((h for h in hospitals if "Sion" in h.get("name", "")), None)
        if sion_h:
            sion_h["occupied"]["icu"] = sion_h["capacity"]["icu"]
            sion_h["status"] = "full"

    elif e_type == "blood":
        for h in hospitals:
            h["blood"]["O-"] = max(0, h["blood"].get("O-", 10) - 8)

    elif e_type == "ambulance":
        amb = next((a for a in ambulances if a.get("id") == "AMB-04" or a.get("status") == "idle"), None)
        if amb:
            amb["status"] = "broken"
            amb["assignedIncidentId"] = None

    elif e_type == "casualty":
        hindmata = next((i for i in incidents if i.get("area") == "Hindmata"), None)
        if hindmata:
            hindmata["redPatients"] += 10
            hindmata["patientCount"] += 20
            hindmata["urgency"] = 95

    elif e_type == "road":
        if "Bridge" in event["title"]:
            for r in roads:
                if (r.get("from") == "Sion" and r.get("to") == "Dadar") or (r.get("from") == "Dadar" and r.get("to") == "Sion"):
                    r["condition"] = "blocked"
        elif "Reopening" in event["title"]:
            for r in roads:
                if r.get("from") == "Bandra" or r.get("to") == "Bandra":
                    r["condition"] = "open"

    elif e_type == "power":
        cooper = next((h for h in hospitals if "Cooper" in h.get("name", "")), None)
        if cooper:
            cooper["status"] = "power_failure"

    elif e_type == "surge":
        kurla = next((i for i in incidents if i.get("area") == "Kurla"), None)
        if kurla:
            kurla["redPatients"] += 8
            kurla["patientCount"] += 15

    elif e_type == "funds":
        funds.append({
            "id": f"F{len(funds)+1}",
            "donor": "Emergency Response Consortium",
            "amount": 50000000.0,
            "purpose": "Logistics & Trauma Care Pool",
            "stage": "released",
            "recipient": "Emergency Pool",
            "timestamp": event.get("time", 12.0)
        })

    elif e_type == "supply":
        o2 = next((s for s in supplies if "Oxygen" in s.get("name", "")), None)
        if o2:
            o2["status"] = "stuck"

    return {
        "alert": alert,
        "affected_type": e_type
    }
