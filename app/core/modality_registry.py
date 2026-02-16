MODALITY_REGISTRY = {
    "accelerometer": {
        "columns": ["acc_x", "acc_y", "acc_z"],
        "weight": 0.25,
        "interp": "linear",
    },
    "gyroscope": {
        "columns": ["gyro_x", "gyro_y", "gyro_z"],
        "weight": 0.20,
        "interp": "linear",
    },
    "magnetometer": {
        "columns": ["mag_x", "mag_y", "mag_z"],
        "weight": 0.10,
        "interp": "linear",
    },
    "gps": {
        "columns": ["gps_lat", "gps_lon", "gps_speed", "gps_alt"],
        "weight": 0.15,
        "interp": "linear",
    },
    "barometer": {
        "columns": ["pressure"],
        "weight": 0.10,
        "interp": "linear",
    },
    "heart_rate": {
        "columns": ["heart_rate"],
        "weight": 0.10,
        "interp": "ffill",
    },
    "light": {
        "columns": ["light_lux"],
        "weight": 0.05,
        "interp": "linear",
    },
    "proximity": {
        "columns": ["proximity"],
        "weight": 0.05,
        "interp": "ffill",
    },
}
