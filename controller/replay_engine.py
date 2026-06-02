import time
import threading
import logging
from kortex_api.autogen.messages import Base_pb2
from utils.event_bus import EventBus

class ReplayEngine:
    """Manages the execution of motion sequences on the robot arm in a separate background thread."""
    def __init__(self, hardware):
        self.hardware = hardware
        self.logger = logging.getLogger("ReplayEngine")
        self.is_replaying = False
        self.stop_requested = False

    def start(self, sequence, on_finished_callback=None):
        """Launches sequence execution in a background daemon thread."""
        if self.is_replaying:
            return False
            
        self.stop_requested = False
        self.is_replaying = True
        
        thread = threading.Thread(
            target=self._replay_worker, 
            args=(sequence, on_finished_callback), 
            daemon=True
        )
        thread.start()
        return True

    def stop(self):
        """Sends a stop signal to cancel execution on the next step."""
        self.stop_requested = True

    def _replay_worker(self, sequence, on_finished_callback):
        try:
            self.logger.info("=== START SEQUENCE-REPLAY ===")
            
            # 1. Move back to default position before starting replay
            self.logger.info("Moving back to default position before starting replay...")
            completion_event = self.hardware.move_to_default()
            if completion_event:
                completion_event.wait(timeout=15.0)
                
            if not getattr(self.hardware, '_last_action_success', True):
                raise RuntimeError("Moving to default position failed!")
                
            if self.stop_requested:
                self.logger.info("Replay aborted before sequence start.")
                return
                
            # 2. Pause there for 2.0 seconds
            self.logger.info("Pausing at default position for 2.0s...")
            slept = 0.0
            while slept < 2.0:
                if self.stop_requested:
                    self.logger.info("Replay aborted during pre-run pause.")
                    return
                time.sleep(0.1)
                slept += 0.1
                
            # 3. Play start chime and delay physical execution by 1.0 second
            EventBus.publish("replay_started")
            self.logger.info("Replay start chime played, waiting 1.0s warning countdown before execution...")
            slept = 0.0
            while slept < 1.0:
                if self.stop_requested:
                    self.logger.info("Replay aborted during pre-execution warning delay.")
                    return
                time.sleep(0.1)
                slept += 0.1

            self.logger.info("Replay sequence starting...")

            batch_waypoints = []
            batch_duration = 0.0

            def flush_waypoints():
                nonlocal batch_waypoints, batch_duration
                if not batch_waypoints: 
                    return
                
                # Fetch actual starting joint positions from the hardware telemetry
                reference_pose = getattr(self.hardware.state, 'joint_angles_deg', None)
                if not reference_pose or len(reference_pose) < 6:
                    reference_pose = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                else:
                    reference_pose = list(reference_pose)

                wp_list = Base_pb2.WaypointList()
                wp_list.use_optimal_blending = True
                
                for wp_data in batch_waypoints:
                    wp = wp_list.waypoints.add()
                    
                    # Unwrap target angles relative to the reference_pose to guarantee the shortest path
                    unwrapped_angles = []
                    for i in range(6):
                        ref_angle = reference_pose[i]
                        target_angle = wp_data['pos'][i]
                        
                        diff = target_angle - ref_angle
                        while diff > 180.0: diff -= 360.0
                        while diff < -180.0: diff += 360.0
                        
                        unwrapped_angle = ref_angle + diff
                        unwrapped_angles.append(unwrapped_angle)
                        
                    # Advance the reference_pose to the current target for the next waypoint
                    reference_pose = unwrapped_angles
                    
                    wp.angular_waypoint.angles.extend(unwrapped_angles)
                    wp.angular_waypoint.duration = wp_data['duration_s']
                    if sum(wp_data['max_velocities']) > 0:
                        wp.angular_waypoint.maximum_velocities.extend(wp_data['max_velocities'])

                self.logger.info(f"[BATCH] Send {len(batch_waypoints)} Waypoints to hardware...")
                completion_event = self.hardware.execute_waypoint_list(wp_list)
                
                if completion_event:
                    # Wait for execution with safety padding
                    completion_event.wait(timeout=batch_duration + 5.0) 
                    
                batch_waypoints.clear()
                batch_duration = 0.0

                if not getattr(self.hardware, '_last_action_success', True):
                    raise RuntimeError("WaypointList execution failed!")

            for idx, step in enumerate(sequence):
                if self.stop_requested: 
                    break
                stype = step["type"]

                if stype == "angularwaypoint":
                    batch_waypoints.append(step)
                    batch_duration += step["duration_s"]

                elif stype == "action":
                    flush_waypoints()
                    
                    self.logger.info(f"[STEP {idx}] Send action to hardware...")
                    completion_event = self.hardware.execute_action_pose(
                        step["pos"], 
                        step["duration_s"], 
                        f"Step_{idx}"
                    )
                    
                    if completion_event:
                        completion_event.wait(timeout=step["duration_s"] + 5.0)
                        
                    if not getattr(self.hardware, '_last_action_success', True):
                        raise RuntimeError("Action execution failed!")

                elif stype == "gripper":
                    flush_waypoints()
                    self.logger.info(f"[STEP {idx}] Send gripper action to hardware...")
                    completion_event = self.hardware.execute_gripper_action(
                        step.get("gripper_state", "open"),
                        step.get("gripper_duration", "medium"),
                        step.get("gripper_target_pos", None),
                        step.get("gripper_speed_ratio", None)
                    )
                    
                    if completion_event:
                        completion_event.wait(timeout=step.get("duration_s", 1.5) + 5.0)
                        
                    if not getattr(self.hardware, '_last_action_success', True):
                        raise RuntimeError("Gripper action failed!")

                elif stype == "pause":
                    flush_waypoints()
                    p_time = step["duration_s"]
                    self.logger.info(f"[STEP {idx}] PAUSE: {p_time}s")
                    
                    # Sleep in increments so stop requests are responsive during long pauses
                    slept = 0.0
                    while slept < p_time:
                        if self.stop_requested:
                            break
                        time.sleep(0.1)
                        slept += 0.1

            flush_waypoints()
            if not self.stop_requested:
                self.logger.info("=== REPLAY COMPLETED SUCCESSFULLY ===")
                EventBus.publish("replay_finished")
            else:
                self.logger.info("=== REPLAY COMPLETED WITH MANUAL ABORT ===")

        except Exception as e:
            self.logger.error(f"Exception occurred during Replay: {e}")
            self.logger.error("Aborting replay sequence due to execution error.")
            # Trigger audio feedback notification for failure using the standard fault event
            EventBus.publish("fault_detected")
            self.stop_requested = True
        finally:
            self.is_replaying = False
            if on_finished_callback:
                on_finished_callback()
