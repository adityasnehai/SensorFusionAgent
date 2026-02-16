def classify_sensors(columns):

    core = []
    extension = []

    for col in columns:

        lower = col.lower()

        if "acc" in lower:
            core.append(col)

        elif "gyro" in lower:
            core.append(col)

        elif any(x in lower for x in ["mag", "gps", "lat", "lon", "hr", "eda", "temp", "screen"]):
            extension.append(col)

        else:
            extension.append(col)

    return core, extension
