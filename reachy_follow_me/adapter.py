"""Shared, explicit anatomical naming. SDK order is [RIGHT, LEFT], radians.

The SDK MuJoCo backend negates antenna targets. Resolve simulator actuators by
name, not a stale positional comment in an older SDK backend.
"""
import math

LIMITS = {"yaw": (-35, 35), "left": (0, 70), "right": (0, 70)}

def checked_target(data):
    angles = data.get("angles")
    if not isinstance(angles, dict) or set(angles) != set(LIMITS) or type(data.get("active")) is not bool:
        raise ValueError("Expected three angles and active boolean")
    for name, (lo, hi) in LIMITS.items():
        v = angles[name]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError("Invalid bounded angle")
    return {k: float(v) for k, v in angles.items()}

def sdk_antennas(angles):
    return [math.radians(angles["right"] - 70), math.radians(70 - angles["left"])]

def classroom_antennas(sdk):
    return {"right": 70 + math.degrees(sdk[0]), "left": 70 - math.degrees(sdk[1])}

def mujoco_antennas(angles):
    right, left = sdk_antennas(angles)
    return {"right_antenna": -right, "left_antenna": -left}
