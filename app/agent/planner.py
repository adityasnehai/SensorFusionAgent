from app.core.unit_detection import detect_acc_unit, get_scaling_factor


class Planner:

    def detect_conflicts(self, df):

        conflicts = []

        # Unit detection remains advisory; agent runtime decides whether to apply it.
        try:
            detected_unit = detect_acc_unit(df)
        except Exception:
            detected_unit = "unknown"

        if detected_unit == "g":
            factor = get_scaling_factor(detected_unit)

            conflicts.append({
                "type": "unit_auto_detect",
                "action": "scale_all_acc",
                "factor": factor,
                "reason": "accelerometer detected in g, normalize to m/s^2",
            })

        return conflicts
