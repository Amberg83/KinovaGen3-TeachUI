import os
import sys
import logging

# Ensure root directory is in the path so we can import model.study_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model.study_manager import StudyManager

# Configure basic logging to avoid cluttering or missing handlers warnings
logging.basicConfig(level=logging.WARNING)

def main():
    # Instantiate StudyManager in study_mode=False (by passing empty pid) to avoid side effects
    # like creating session result directories or log handlers.
    manager = StudyManager(participant_id="")
    
    # Load tutorials and experimental referents using the study manager's existing methods
    tutorials = manager._load_or_create_tutorials()
    referents = manager._load_or_create_referents()
    
    # Analyze if tutorials count towards the ordering
    # Looking at StudyManager.__init__:
    # self.tasks = self.tutorials + ordered_experimental
    # and latin_order is calculated using len(self.experimental_tasks).
    # Thus, tutorials are prepended directly and do not count towards the Latin square ordering.
    tutorials_count_towards_ordering = False
    num_ordering_tasks = len(referents)
    
    output_lines = []
    output_lines.append("=== Balanced Latin Square Task Ordering Analysis ===")
    output_lines.append(f"Do tutorials count towards the ordering? {'Yes' if tutorials_count_towards_ordering else 'No'}")
    output_lines.append(f"Number of tasks that count towards the ordering: {num_ordering_tasks}")
    output_lines.append("")
    
    output_lines.append("Loaded Tutorials (Prepended first, in fixed order):")
    for t in tutorials:
        output_lines.append(f"  - ID {t['id']}: {t['name']}")
    output_lines.append("")
    
    output_lines.append("Loaded Experimental Tasks (Balanced Latin Square Ordered):")
    for r in referents:
        output_lines.append(f"  - ID {r['id']}: {r['name']}")
    output_lines.append("")
    
    output_lines.append("=== Task Order for Participants (PID 1 to PID 32) ===")
    
    order_to_pids = {}
    
    for pid in range(1, 33):
        # Generate Williams' Latin Square ordering for this PID
        latin_order = manager._generate_balanced_latin_square_order(pid, num_ordering_tasks)
        ordered_experimental = [referents[idx] for idx in latin_order]
        
        # Combine them just like StudyManager does
        full_task_order = tutorials + ordered_experimental
        
        # Track the sequence of task IDs to group identical orders
        task_id_sequence = tuple(task['id'] for task in full_task_order)
        if task_id_sequence not in order_to_pids:
            order_to_pids[task_id_sequence] = []
        order_to_pids[task_id_sequence].append(pid)
        
        output_lines.append(f"PID {pid}:")
        for i, task in enumerate(full_task_order, 1):
            is_tutorial = (task in tutorials)
            task_type = "Tutorial" if is_tutorial else "Experimental"
            output_lines.append(f"  Task {i:02d}: {task['name']} (ID: {task['id']}, Type: {task_type})")
        output_lines.append("-" * 50)
    
    # Analyze and group identical sequences
    output_lines.append("")
    output_lines.append("=== Analysis of Duplicate Task Orders ===")
    output_lines.append("Below are the PIDs grouped by identical task sequence:")
    
    group_idx = 1
    for task_ids, pids in order_to_pids.items():
        # Get names for sequence display
        task_names = []
        for tid in task_ids:
            # find corresponding task in tutorials or referents
            match = next((t for t in tutorials if t['id'] == tid), None) or next((r for r in referents if r['id'] == tid), None)
            if match:
                task_names.append(match['name'])
        
        sequence_str = " -> ".join(task_names)
        pids_str = ", ".join(f"PID {p}" for p in pids)
        output_lines.append(f"Group {group_idx}:")
        output_lines.append(f"  Matching PIDs ({len(pids)}): {pids_str}")
        output_lines.append(f"  Sequence: {sequence_str}")
        output_lines.append("")
        group_idx += 1
        
    output_content = "\n".join(output_lines)
    
    # Print the result to console
    print(output_content)
    
    # Save the result to study_results/latin_square_order_results.txt
    results_dir = "study_results"
    os.makedirs(results_dir, exist_ok=True)
    results_path = os.path.join(results_dir, "latin_square_order_results.txt")
    
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(output_content)
        
    print(f"\n[SUCCESS] Task ordering successfully saved to '{results_path}'")

if __name__ == "__main__":
    main()
