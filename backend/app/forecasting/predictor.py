import numpy as np
from sklearn.ensemble import RandomForestRegressor
from app.adapters.mumbai_geo import MUMBAI_AREAS

class DemandForecaster:
    """
    Lightweight Demand Forecasting module for multi-horizon casualty surge prediction (+10m, +20m, +30m).
    Uses RandomForestRegressor with robust statistical fallback.
    """
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=30, random_state=42)
        self._is_fitted = False
        self._bootstrap_synthetic_training()

    def _bootstrap_synthetic_training(self):
        # Synthetic observations: [sim_time, current_red, current_yellow, flooded_roads_count, active_incidents]
        X = []
        y_10 = []
        y_20 = []
        y_30 = []
        rng = np.random.RandomState(42)

        for t in np.linspace(0, 30, 60):
            for red in [5, 12, 20, 35]:
                for flooded in [1, 3, 6, 9]:
                    arrival_rate = 1.2 + (flooded * 0.4) + (red * 0.1)
                    feat = [t, red, red * 1.5, flooded, 5 + int(flooded * 0.8)]
                    X.append(feat)
                    y_10.append(red + arrival_rate * 2.0 + rng.normal(0, 1.5))
                    y_20.append(red + arrival_rate * 4.5 + rng.normal(0, 2.5))
                    y_30.append(red + arrival_rate * 7.0 + rng.normal(0, 4.0))

        self.model.fit(np.array(X), np.column_stack([y_10, y_20, y_30]))
        self._is_fitted = True

    def predict_demand(
        self,
        sim_time: float,
        incidents: list[dict],
        roads: list[dict]
    ) -> dict:
        total_red = sum(i.get("redPatients", 0) for i in incidents)
        total_yellow = sum(i.get("yellowPatients", 0) for i in incidents)
        flooded_count = sum(1 for r in roads if r.get("condition") == "flooded")
        active_count = len([i for i in incidents if i.get("status") in ("active", "assigned")])

        features = np.array([[sim_time, total_red, total_yellow, flooded_count, active_count]])

        if self._is_fitted:
            preds = self.model.predict(features)[0]
            p10 = max(total_red, int(round(preds[0])))
            p20 = max(p10, int(round(preds[1])))
            p30 = max(p20, int(round(preds[2])))
        else:
            # Statistical fallback
            rate = 1.5 + flooded_count * 0.5
            p10 = int(round(total_red + rate * 1.8))
            p20 = int(round(total_red + rate * 4.0))
            p30 = int(round(total_red + rate * 6.5))

        # Hotspots identification
        area_loads = {}
        for inc in incidents:
            area = inc.get("area", "Sion")
            area_loads[area] = area_loads.get(area, 0) + inc.get("redPatients", 0) * 2 + inc.get("yellowPatients", 0)

        hotspots = sorted(
            [{"area": a, "riskScore": round(min(100, s * 2.5), 1), "coordinates": MUMBAI_AREAS.get(a, {"lat":19.0,"lng":72.8})} for a, s in area_loads.items()],
            key=lambda x: x["riskScore"],
            reverse=True
        )[:4]

        # Recommended pre-positioning
        prepositioning = []
        if hotspots:
            top_spot = hotspots[0]["area"]
            prepositioning.append({
                "targetArea": top_spot,
                "recommendedAssets": ["2 ICU Ambulances", "1 Flood Rescue Boat", "50 Oxygen Cylinders"],
                "reason": f"Projected casualty growth (+{p20 - total_red} critical patients in 20m window)"
            })
        if len(hotspots) > 1:
            prepositioning.append({
                "targetArea": hotspots[1]["area"],
                "recommendedAssets": ["1 Advanced Ambulance", "500 IV Fluids"],
                "reason": "Secondary saturation buffer for peripheral spillover"
            })

        return {
            "currentDemand": total_red,
            "forecast10m": p10,
            "forecast20m": p20,
            "forecast30m": p30,
            "confidence": 0.88 if self._is_fitted else 0.72,
            "hotspots": hotspots,
            "recommendedPrepositioning": prepositioning,
            "disclaimer": "SIMULATED PREDICTIONS — Machine Learning Model (RandomForestRegressor)"
        }
