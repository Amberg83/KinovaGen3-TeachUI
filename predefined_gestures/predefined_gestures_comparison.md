# Predefined Gestures Comparison Analysis

This document provides a precise, step-by-step structural and behavioral analysis comparing the transitions between the four core predefined gestures (`1.json` $\rightarrow$ `2.json` $\rightarrow$ `3.json` $\rightarrow$ `4.json`).

---

## Workspace Directory & File Status
*   **Path**: `predefined_gestures/`
*   **Gestures Identified**:
    *   [1.json](file:///c:/Users/roman/Documents/GitProjects/KinovaGen3-TeachUI/predefined_gestures/1.json): **6 steps** (base trajectory sequence)
    *   [2.json](file:///c:/Users/roman/Documents/GitProjects/KinovaGen3-TeachUI/predefined_gestures/2.json): **8 steps** (sequence with added gripper action and stabilization pause)
    *   [3.json](file:///c:/Users/roman/Documents/GitProjects/KinovaGen3-TeachUI/predefined_gestures/3.json): **8 steps** (sequence with optimized trajectory duration, accelerated gripper, and lengthened pause)
    *   [4.json](file:///c:/Users/roman/Documents/GitProjects/KinovaGen3-TeachUI/predefined_gestures/4.json): **8 steps** (sequence utilizing blended angular waypoints with optimized joint durations)

---

## Step-by-Step Step Mapping Table

| Step Index | Gesture 1 (`1.json`) | Gesture 2 (`2.json`) | Gesture 3 (`3.json`) | Gesture 4 (`4.json`) |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `action` (0.12s) | `action` (0.12s) | `action` (0.12s) | `action` (0.12s) |
| **2** | `action` (2.81s) | `action` (2.81s) | `action` (1.40s) <br> *(Accelerated)* | `action` (1.40s) |
| **3** | `action` (1.23s) | `gripper` (1.50s) <br> *(Medium speed)* | `gripper` (1.50s) <br> *(Fast speed)* | `gripper` (1.50s) |
| **4** | `action` (2.25s) | `action` (1.23s) | `action` (1.23s) | `action` (1.23s) |
| **5** | `action` (2.25s) | `action` (2.25s) | `action` (2.25s) | `action` (2.25s) |
| **6** | `action` (2.25s) | `pause` (2.00s) <br> *(Added)* | `pause` (4.00s) <br> *(Lengthened)* | `pause` (4.00s) |
| **7** | — | `action` (2.25s) | `action` (2.25s) | `angularwaypoint` (1.70s) <br> *(Blended & Fast)* |
| **8** | — | `action` (2.25s) | `action` (2.25s) | `angularwaypoint` (1.70s) <br> *(Blended & Fast)* |

---

## Detailed Transition Breakdown

### 1. Gesture 1 $\rightarrow$ Gesture 2: Added Gripper Control & Pause Separation
Gesture 2 expands the sequence from **6 steps to 8 steps** by inserting physical interactions:
*   **Step 3 (Inserted Gripper Command)**:
    *   Adds a `"gripper"` step to close the fingers (`gripper_target_pos = 100.0%`).
    *   Configured with `"medium"` speed duration (`gripper_speed_ratio = 0.5`).
*   **Step 6 (Inserted Stabilization Pause)**:
    *   Adds a `"pause"` step lasting **`2.0` seconds** right after the first motion segment, stabilizing the end-effector.
*   *Note: Because of these insertions, the original motion steps shift down in index.*

---

### 2. Gesture 2 $\rightarrow$ Gesture 3: Motion Speedups & Pause Adjustment
Gesture 3 maintains the identical 8-step structure of Gesture 2 but optimizes velocities and time allocations:
*   **Step 2 Acceleration**:
    *   The second motion segment's duration is halved from `2.81`s to **`1.40`s** (approximately 2x speedup).
*   **Step 3 Gripper Speedup**:
    *   The gripper closure transition is accelerated from `"medium"` (`gripper_speed_ratio = 0.5`) to `"fast"` (`gripper_speed_ratio = 0.0`, direct positioning).
*   **Step 6 Pause Extension**:
    *   The stabilization pause is increased from `2.0` seconds to **`4.0` seconds** to allow more delay in the cycle.

---

### 3. Gesture 3 $\rightarrow$ Gesture 4: Blended Trajectory Conversion
Gesture 4 maintains the identical steps, gripper settings, and pauses of Gesture 3 but optimizes the final movements using joint-level path blending:
*   **Steps 7 & 8 Controller Type Optimization**:
    *   Changed from standard discrete `"action"` steps to **`"angularwaypoint"`** steps.
    *   This enables the Kinova Kortex controller's **optimal blending algorithm** (`use_optimal_blending = True`), allowing the joints to transition fluidly between the two final poses without stopping.
*   **Steps 7 & 8 Duration Reduction**:
    *   The movement durations for both steps are reduced from `2.25`s to **`1.70`s**, further accelerating the final phase of the gesture.
