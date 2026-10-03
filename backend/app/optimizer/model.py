import math

def logistic_survival_prob(triage_class: str, treatment_time_min: float) -> float:
    """
    Logistic survival curve S(c, t) = S0 / (1 + exp(k * (t - t50)))
    - Red: S0 = 0.95, t50 = 60 min, k = 0.07
    - Yellow: S0 = 0.98, t50 = 240 min, k = 0.02
    - Green: S0 = 0.995, t50 = 720 min, k = 0.005
    - Black: 0.0 (expectant / no transport)
    """
    if triage_class == "black":
        return 0.0
    params = {
        "red":    (0.95, 60.0, 0.07),
        "yellow": (0.98, 240.0, 0.02),
        "green":  (0.995, 720.0, 0.005),
    }
    s0, t50, k = params.get(triage_class, params["yellow"])
    try:
        val = s0 / (1.0 + math.exp(k * (treatment_time_min - t50)))
        return max(0.0, min(1.0, val))
    except OverflowError:
        return 0.0


def calculate_survival_proxy(
    triage_class: str,
    severity_score: float, # 0.0 to 1.0
    untreated_time_min: float,
    expected_eta_min: float,
    hospital_specialty_match: bool,
    icu_available: bool,
    blood_sufficient: bool,
    hospital_overloaded: bool
) -> float:
    """
    Survival probability computed via logistic curve and clinical capability multipliers.
    """
    total_time = max(1.0, untreated_time_min + expected_eta_min)
    base_survival = logistic_survival_prob(triage_class, total_time)

    if triage_class == 'black':
        return 0.0

    if triage_class == 'red':
        capability = 0.5
        if hospital_specialty_match:
            capability += 0.20
        if icu_available:
            capability += 0.20
        if blood_sufficient:
            capability += 0.10
        if hospital_overloaded:
            capability *= 0.65
        benefit = min(1.0, base_survival * capability * (1.0 + severity_score * 0.15))
        return round(benefit, 4)

    elif triage_class == 'yellow':
        capability = 0.7
        if hospital_specialty_match:
            capability += 0.15
        if not hospital_overloaded:
            capability += 0.15
        benefit = min(1.0, base_survival * capability)
        return round(benefit, 4)

    else:
        # Green / Minor
        return round(base_survival, 4)

