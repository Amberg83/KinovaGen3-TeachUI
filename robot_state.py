from dataclasses import dataclass, field
from typing import List

@dataclass
class RobotState:
    """Data container encapsulating the complete current state of the Kinova Gen3 robot."""
    
    # General Connection Status
    is_connected: bool = False
    ip: str = ""
    dof: int = 0
    
    # Base (Controller) Status
    has_fault: bool = False
    fault_bank_a: int = 0
    fault_bank_b: int = 0
    control_mode: int = 0         
    command_mode: int = 0         
    active_state: int = 0         
    
    # Cartesian Space (TCP)
    tcp_position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    tcp_orientation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    tcp_linear_velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    tcp_angular_velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    
    # Wrench (Forces and Torques)
    force: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    torque: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    
    # Joint Space (Actuators)
    joint_angles_deg: List[float] = field(default_factory=list)
    joint_velocities: List[float] = field(default_factory=list)
    joint_torques: List[float] = field(default_factory=list)
    joint_currents: List[float] = field(default_factory=list)
    joint_temperatures: List[float] = field(default_factory=list)
    joint_voltage: List[float] = field(default_factory=list)