def evaluate(state, result, threshold=2):
    if threshold < 1:
        raise ValueError("threshold must be at least 1")

    new_state = state.copy()

    if result["healthy"]:
        new_state["consecutive_failures"] = 0

        if new_state["incident_open"]:
            new_state["incident_open"] = False
            return new_state, "RECOVERED"

        return new_state, None

    new_state["consecutive_failures"] += 1

    if (
        new_state["consecutive_failures"] >= threshold
        and not new_state["incident_open"]
    ):
        new_state["incident_open"] = True
        return new_state, "INCIDENT_OPENED"

    return new_state, None