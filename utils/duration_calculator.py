import math
import warnings

def calculate_min_safe_duration(target_pos, predecessor_pos):
    """
    [DEPRECATED] Computes the physical minimum safe duration (seconds) for moving between two joint positions.
    Please use calculate_min_trajectory_duration or calculate_waypoint_durations instead.
    """
    warnings.warn(
        "calculate_min_safe_duration is deprecated. Use calculate_min_trajectory_duration or calculate_waypoint_durations instead.",
        DeprecationWarning,
        stacklevel=2
    )
    if not target_pos or not predecessor_pos or len(target_pos) != len(predecessor_pos):
        return 0.6
        
    # Cruising Speed: 55.0 deg/s, Ramp Overhead: 0.6s
    V_MAX = 49.5
    T_OVERHEAD = 0.5
    
    max_diff = 0.0
    for t, p in zip(target_pos, predecessor_pos):
        diff = t - p
        while diff > 180.0: diff -= 360.0
        while diff < -180.0: diff += 360.0
        max_diff = max(max_diff, abs(diff))
        
    return T_OVERHEAD + (max_diff / V_MAX)

from enum import Enum

class DurationSpeed(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"

    @property
    def multiplier(self) -> float:
        if self == DurationSpeed.FAST:
            return 1.0
        elif self == DurationSpeed.MEDIUM:
            return 2.0
        elif self == DurationSpeed.SLOW:
            return 4.0
        return 1.0

class DurationConfig:
    """
    Configuration parameter bank for trajectory and waypoint list duration estimators.
    Can be dynamically modified/overridden at runtime if needed.
    """
    # Time Buffer (safety margin in seconds)
    TIME_BUFFER = 0.05

    # Safety scaling factors to absorb spline blending overshoots
    SAFETY_FACTOR_ACTION = 1.0
    SAFETY_FACTOR_WAYPOINT = 1.6

    # Default baseline speeds and accelerations for 6-DOF Kinova Gen3 robot
    # Large actuators (Joints 1-3)
    VEL_LARGE = 80.0
    ACCEL_LARGE = 297.94

    # Small actuators (Joints 4-6)
    VEL_SMALL = 70.0
    ACCEL_SMALL = 572.96


def calculate_min_trajectory_duration(start_angles, end_angles, time_buffer=None, speed="fast"):
    """
    Calculates the minimum feasible duration for a movement between two angular 
    positions for a 6-DOF Kinova Gen3 robot based on custom web app limits, scaled by speed multiplier.
    """
    if len(start_angles) != 6 or len(end_angles) != 6:
        raise ValueError("Must provide exactly 6 joint angles.")

    if time_buffer is None:
        time_buffer = DurationConfig.TIME_BUFFER

    max_vel_large = DurationConfig.VEL_LARGE
    max_accel_large = DurationConfig.ACCEL_LARGE
    max_vel_small = DurationConfig.VEL_SMALL
    max_accel_small = DurationConfig.ACCEL_SMALL
    safety_factor = DurationConfig.SAFETY_FACTOR_ACTION

    min_durations = []

    for i in range(6):
        start = start_angles[i]
        end = end_angles[i]
        
        # Assign correct limits based on joint index and scale by safety_factor
        if i < 3:
            v_max = max_vel_large / safety_factor
            a_max = max_accel_large / safety_factor
        else:
            v_max = max_vel_small / safety_factor
            a_max = max_accel_small / safety_factor
        
        # Shortest path wrapping to [-180, 180] range
        delta_theta = end - start
        while delta_theta > 180.0: delta_theta -= 360.0
        while delta_theta < -180.0: delta_theta += 360.0
        distance = abs(delta_theta)
        
        if distance == 0:
            min_durations.append(0.0)
            continue
            
        # Angle required to accelerate to max speed and decelerate to 0
        angle_to_reach_max_speed = (v_max ** 2) / a_max
        
        if distance < angle_to_reach_max_speed:
            # Triangular profile (Joint never hits its max speed limit)
            t = 2 * math.sqrt(distance / a_max)
        else:
            # Trapezoidal profile (Joint hits max speed and cruises)
            t = (distance / v_max) + (v_max / a_max)
            
        min_durations.append(t)

    # The entire arm must take the time of its slowest joint
    minimum_safe_time = max(min_durations)
    base_duration = minimum_safe_time + time_buffer
    
    # Resolve the duration multiplier based on speed Enum
    try:
        speed_enum = DurationSpeed(speed)
    except ValueError:
        speed_enum = DurationSpeed.FAST
        
    return base_duration * speed_enum.multiplier


def calculate_waypoint_durations(waypoints, time_buffer=None, speed="fast"):
    """
    Calculates the minimum feasible durations for a continuous list of angular waypoints, scaled by speed multiplier.
    
    :param waypoints: List of poses, where each pose is a list of 6 joint angles in degrees.
                      Example: [[pose1], [pose2], [pose3]]
    :param time_buffer: Safety margin to prevent API float-rounding rejections.
    :param speed: The speed multiplier to apply ("fast", "medium", "slow").
    :return: A list of safe duration constraints (in seconds) for each segment.
    """
    if not waypoints or len(waypoints) < 2:
        return []

    if time_buffer is None:
        time_buffer = DurationConfig.TIME_BUFFER

    max_vel_large = DurationConfig.VEL_LARGE
    max_accel_large = DurationConfig.ACCEL_LARGE
    max_vel_small = DurationConfig.VEL_SMALL
    max_accel_small = DurationConfig.ACCEL_SMALL
    safety_factor = DurationConfig.SAFETY_FACTOR_WAYPOINT

    durations = []
    
    for j in range(len(waypoints) - 1):
        segment_times = []
        
        for i in range(6):
            # Scale down physical limits to safe planning limits to absorb splining overshoots.
            if i < 3:
                v_max = max_vel_large / safety_factor
                a_max = max_accel_large / safety_factor
            else:
                v_max = max_vel_small / safety_factor
                a_max = max_accel_small / safety_factor
            
            curr_angle = waypoints[j][i]
            next_angle = waypoints[j+1][i]
            
            is_first_segment = (j == 0)
            is_last_segment = (j == len(waypoints) - 2)
            
            # Shortest path wrapping to [-180, 180] range
            delta_theta = next_angle - curr_angle
            while delta_theta > 180.0: delta_theta -= 360.0
            while delta_theta < -180.0: delta_theta += 360.0
            distance = abs(delta_theta)
            
            if distance == 0:
                segment_times.append(0.0)
                continue
            
            starts_from_rest = is_first_segment
            if not is_first_segment:
                prev_angle = waypoints[j-1][i]
                prev_delta = curr_angle - prev_angle
                while prev_delta > 180.0: prev_delta -= 360.0
                while prev_delta < -180.0: prev_delta += 360.0
                if delta_theta * prev_delta < 0:
                    starts_from_rest = True
                    
            ends_at_rest = is_last_segment
            if not is_last_segment:
                next_next_angle = waypoints[j+2][i]
                next_delta = next_next_angle - next_angle
                while next_delta > 180.0: next_delta -= 360.0
                while next_delta < -180.0: next_delta += 360.0
                if next_delta * delta_theta < 0:
                    ends_at_rest = True

            t = distance / v_max
            
            if starts_from_rest:
                t += v_max / (2 * a_max)
            if ends_at_rest:
                t += v_max / (2 * a_max)
                
            if starts_from_rest and ends_at_rest:
                angle_to_reach_max = (v_max ** 2) / a_max
                if distance < angle_to_reach_max:
                    t = 2 * math.sqrt(distance / a_max)
                    
            segment_times.append(t)
            
        segment_safe_time = max(segment_times)
        durations.append(segment_safe_time + time_buffer)
        
    # Resolve the duration multiplier based on speed Enum
    try:
        speed_enum = DurationSpeed(speed)
    except ValueError:
        speed_enum = DurationSpeed.FAST
        
    multiplier = speed_enum.multiplier
    return [d * multiplier for d in durations]
