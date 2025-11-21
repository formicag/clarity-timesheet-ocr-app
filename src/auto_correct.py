"""
Enhanced constraint-based column correction with multiple strategies.
"""
from typing import Dict, List, Any, Tuple, Optional
import copy
from itertools import permutations, combinations


def calculate_daily_sums(data: Dict[str, Any]) -> List[float]:
    """Calculate daily sums from all projects."""
    daily_sums = [0.0] * 7
    for proj in data.get('projects', []):
        for i, day_entry in enumerate(proj.get('hours_by_day', [])):
            daily_sums[i] += float(day_entry.get('hours', 0))
    return daily_sums


def is_valid(data: Dict[str, Any]) -> bool:
    """Check if daily sums match header totals."""
    header_totals = data.get('daily_totals', [0] * 7)
    daily_sums = calculate_daily_sums(data)
    return all(abs(header_totals[i] - daily_sums[i]) < 0.01 for i in range(7))


def get_mismatch_info(data: Dict[str, Any]) -> Tuple[List[int], List[int], List[float]]:
    """Get info about which days are over/under and by how much."""
    header_totals = data.get('daily_totals', [0] * 7)
    daily_sums = calculate_daily_sums(data)

    over_days = []
    under_days = []
    diffs = []

    for i in range(7):
        diff = daily_sums[i] - header_totals[i]
        if abs(diff) >= 0.01:
            diffs.append(diff)
            if diff > 0:
                over_days.append(i)
            else:
                under_days.append(i)

    return over_days, under_days, diffs


def try_simple_move(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Try moving hours from over days to under days within same project."""
    over_days, under_days, _ = get_mismatch_info(data)
    if not over_days or not under_days:
        return (False, data, "")

    projects = data.get('projects', [])
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for proj_idx, proj in enumerate(projects):
        hours = [float(d.get('hours', 0)) for d in proj['hours_by_day']]

        for over_idx in over_days:
            if hours[over_idx] == 0:
                continue

            for under_idx in under_days:
                if hours[under_idx] > 0:
                    continue

                corrected = copy.deepcopy(data)
                corrected_proj = corrected['projects'][proj_idx]
                val = corrected_proj['hours_by_day'][over_idx]['hours']
                corrected_proj['hours_by_day'][under_idx]['hours'] = val
                corrected_proj['hours_by_day'][over_idx]['hours'] = '0'

                if is_valid(corrected):
                    msg = f"✓ Moved {val}h from {days[over_idx]} to {days[under_idx]} in {proj['project_code']}"
                    return (True, corrected, msg)

    return (False, data, "")


def try_swap_between_projects(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Try swapping hours between different projects."""
    over_days, under_days, _ = get_mismatch_info(data)
    if not over_days or not under_days:
        return (False, data, "")

    projects = data.get('projects', [])
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for proj1_idx in range(len(projects)):
        for proj2_idx in range(len(projects)):
            if proj1_idx == proj2_idx:
                continue

            proj1_hours = [float(d.get('hours', 0)) for d in projects[proj1_idx]['hours_by_day']]
            proj2_hours = [float(d.get('hours', 0)) for d in projects[proj2_idx]['hours_by_day']]

            for over_idx in over_days:
                for under_idx in under_days:
                    if proj1_hours[over_idx] > 0 and proj2_hours[under_idx] == 0:
                        corrected = copy.deepcopy(data)
                        val = corrected['projects'][proj1_idx]['hours_by_day'][over_idx]['hours']
                        corrected['projects'][proj1_idx]['hours_by_day'][over_idx]['hours'] = '0'
                        corrected['projects'][proj2_idx]['hours_by_day'][under_idx]['hours'] = val

                        if is_valid(corrected):
                            p1 = projects[proj1_idx]['project_code']
                            p2 = projects[proj2_idx]['project_code']
                            msg = f"✓ Moved {val}h from {p1}'s {days[over_idx]} to {p2}'s {days[under_idx]}"
                            return (True, corrected, msg)

    return (False, data, "")


def try_complex_redistribution(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Try multiple simultaneous moves to fix complex misalignments."""
    over_days, under_days, _ = get_mismatch_info(data)
    if not over_days or not under_days:
        return (False, data, "")

    projects = data.get('projects', [])
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # Strategy 1: Try all combinations of 2 simultaneous moves across different projects
    for proj1_idx in range(len(projects)):
        for proj2_idx in range(len(projects)):
            if proj1_idx == proj2_idx:
                continue

            proj1_hours = [float(d.get('hours', 0)) for d in projects[proj1_idx]['hours_by_day']]
            proj2_hours = [float(d.get('hours', 0)) for d in projects[proj2_idx]['hours_by_day']]

            # Try moving from over days to under days in both projects
            for over1_idx in over_days:
                if proj1_hours[over1_idx] == 0:
                    continue

                for under1_idx in under_days:
                    if proj1_hours[under1_idx] > 0:
                        continue

                    for under2_idx in under_days:
                        if under2_idx == under1_idx:
                            continue
                        if proj2_hours[under2_idx] > 0:
                            continue

                        # Try adding hour to proj2's under2 day
                        temp = copy.deepcopy(data)

                        # Move 1: proj1's over→under
                        val1 = temp['projects'][proj1_idx]['hours_by_day'][over1_idx]['hours']
                        temp['projects'][proj1_idx]['hours_by_day'][under1_idx]['hours'] = val1
                        temp['projects'][proj1_idx]['hours_by_day'][over1_idx]['hours'] = '0'

                        # Move 2: Add same value to proj2's under day
                        temp['projects'][proj2_idx]['hours_by_day'][under2_idx]['hours'] = val1

                        if is_valid(temp):
                            p1 = projects[proj1_idx]['project_code']
                            p2 = projects[proj2_idx]['project_code']
                            msg = f"✓ Multi-fix: Moved {val1}h in {p1} ({days[over1_idx]}→{days[under1_idx]}) and added {val1}h to {p2}'s {days[under2_idx]}"
                            return (True, temp, msg)

    # Strategy 2: Single move in one project, plus add to another
    for proj1_idx in range(len(projects)):
        proj1_hours = [float(d.get('hours', 0)) for d in projects[proj1_idx]['hours_by_day']]

        for over1_idx in over_days:
            if proj1_hours[over1_idx] == 0:
                continue

            for under1_idx in under_days:
                # Move from over to under in proj1
                temp = copy.deepcopy(data)
                val1 = temp['projects'][proj1_idx]['hours_by_day'][over1_idx]['hours']
                temp['projects'][proj1_idx]['hours_by_day'][under1_idx]['hours'] = val1
                temp['projects'][proj1_idx]['hours_by_day'][over1_idx]['hours'] = '0'

                # Check if this alone fixes it
                if is_valid(temp):
                    msg = f"✓ Moved {val1}h from {days[over1_idx]} to {days[under1_idx]} in {projects[proj1_idx]['project_code']}"
                    return (True, temp, msg)

                # Try adding to another project
                for proj2_idx in range(len(projects)):
                    if proj2_idx == proj1_idx:
                        continue

                    proj2_hours = [float(d.get('hours', 0)) for d in temp['projects'][proj2_idx]['hours_by_day']]

                    for under2_idx in under_days:
                        if under2_idx == under1_idx:
                            continue
                        if proj2_hours[under2_idx] > 0:
                            continue

                        corrected = copy.deepcopy(temp)
                        corrected['projects'][proj2_idx]['hours_by_day'][under2_idx]['hours'] = val1

                        if is_valid(corrected):
                            p1 = projects[proj1_idx]['project_code']
                            p2 = projects[proj2_idx]['project_code']
                            msg = f"✓ Multi-fix: Moved {val1}h in {p1} ({days[over1_idx]}→{days[under1_idx]}) and added {val1}h to {p2}'s {days[under2_idx]}"
                            return (True, corrected, msg)

    return (False, data, "")


def try_proportional_scaling(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Try scaling hours proportionally to match header (for missing subtask case)."""
    header_totals = data.get('daily_totals', [0] * 7)
    daily_sums = calculate_daily_sums(data)

    # Check if ALL mismatches are proportional (same ratio)
    ratios = []
    mismatch_days = []
    for i in range(7):
        if abs(header_totals[i] - daily_sums[i]) >= 0.01:
            if daily_sums[i] > 0:
                ratio = header_totals[i] / daily_sums[i]
                ratios.append(ratio)
                mismatch_days.append(i)

    if not ratios:
        return (False, data, "")

    # Check if all ratios are the same (within tolerance)
    avg_ratio = sum(ratios) / len(ratios)
    if all(abs(r - avg_ratio) < 0.1 for r in ratios):
        # All days are off by same proportion - likely missing subtask
        corrected = copy.deepcopy(data)

        # Scale all projects proportionally
        for proj in corrected['projects']:
            for day_idx in mismatch_days:
                old_val = float(proj['hours_by_day'][day_idx]['hours'])
                if old_val > 0:
                    new_val = old_val * avg_ratio
                    proj['hours_by_day'][day_idx]['hours'] = f"{new_val:.2f}"

        if is_valid(corrected):
            msg = f"✓ Scaled hours by {avg_ratio:.2f}x (likely missing subtask - extracted partial data)"
            return (True, corrected, msg)

    return (False, data, "")


def enhanced_correct(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """
    Enhanced auto-correction with multiple strategies.

    Tries corrections in order of complexity:
    1. Simple moves within project
    2. Swaps between projects
    3. Proportional scaling (missing subtask)
    4. Complex multi-move redistribution
    """
    if is_valid(data):
        return (False, data, "No correction needed")

    # Strategy 1: Simple move
    success, corrected, msg = try_simple_move(data)
    if success:
        return (True, corrected, msg + " [Strategy: Simple Move]")

    # Strategy 2: Swap between projects
    success, corrected, msg = try_swap_between_projects(data)
    if success:
        return (True, corrected, msg + " [Strategy: Project Swap]")

    # Strategy 3: Proportional scaling
    success, corrected, msg = try_proportional_scaling(data)
    if success:
        return (True, corrected, msg + " [Strategy: Proportional Scaling]")

    # Strategy 4: Complex redistribution
    success, corrected, msg = try_complex_redistribution(data)
    if success:
        return (True, corrected, msg + " [Strategy: Complex Redistribution]")

    # If all strategies fail
    over_days, under_days, _ = get_mismatch_info(data)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    over_str = ', '.join([days[i] for i in over_days])
    under_str = ', '.join([days[i] for i in under_days])
    msg = f"⚠️  Could not auto-correct. Over: [{over_str}], Under: [{under_str}]"
    return (False, data, msg)
