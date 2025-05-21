from ortools.sat.python import cp_model
import pandas as pd

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from collections import defaultdict

# Load data
students_df = pd.read_csv(os.path.join(BASE_DIR, "students.csv"))
courses_df = pd.read_csv(os.path.join(BASE_DIR, "./courses.csv"))
teachers_df = pd.read_csv(os.path.join(BASE_DIR, "./teachers.csv"))
rooms_df = pd.read_csv(os.path.join(BASE_DIR, "./rooms.csv"))

model = cp_model.CpModel()

# Constants
PERIODS = list(range(1, 9))
GRADES_PRIORITY = {"12": 0, "11": 1, "10": 2, "9": 3}
MAX_PERIODS = 8

# Map of teacher to courses and preferred room
teacher_courses = {}
teacher_rooms = {}
for _, row in teachers_df.iterrows():
    for course in row["courses"].split(";"):
        teacher_courses.setdefault(course.strip(), []).append(row["name"])
    teacher_rooms[row["name"]] = row["preferred_room"]

# Generate sections per course
sections = []
section_meta = {}  # Map section_id -> (course, index)
for _, row in courses_df.iterrows():
    course = row["course"]
    num_sections = int(row["max_sections"])
    for i in range(num_sections):
        sec_id = f"{course}_Sec{i+1}"
        sections.append(sec_id)
        section_meta[sec_id] = {
            "course": course,
            "category": row["category"],
            "max_students": int(row["max_students"]),
            "allowed_periods": list(map(int, row["allowed_periods"].split(",")))
        }

# Room and period variable per section
section_period = {}
section_room = {}
section_teacher = {}

for sec_id in sections:
    allowed_periods = section_meta[sec_id]["allowed_periods"]
    section_period[sec_id] = model.NewIntVarFromDomain(
        cp_model.Domain.FromValues(allowed_periods), f"{sec_id}_Period"
    )
    section_room[sec_id] = model.NewIntVar(0, len(rooms_df) - 1, f"{sec_id}_Room")
    section_teacher[sec_id] = model.NewIntVar(0, len(teachers_df) - 1, f"{sec_id}_Teacher")

# Student assignments: student -> section -> boolean variable
student_section_vars = {}
student_course_map = defaultdict(list)

for _, student in students_df.iterrows():
    s_name = student["name"]
    s_grade = str(student["grade"])
    required = student["required_courses"].split(";")
    electives = student["elective_choices"].split(";")
    bibles = student["bible_choices"].split(";")

    all_courses = set(required)
    all_courses.update(electives[:4])  # Top 4 electives
    all_courses.update(bibles[:4])     # Top 4 bible choices

    for sec_id in sections:
        course = section_meta[sec_id]["course"]
        if course in all_courses:
            var = model.NewBoolVar(f"{s_name}_{sec_id}")
            student_section_vars[(s_name, sec_id)] = var
            student_course_map[s_name].append((course, sec_id, var))

# Constraint: each student gets one section per unique course they requested
for s_name in student_course_map:
    courses = defaultdict(list)
    for course, sec_id, var in student_course_map[s_name]:
        courses[course].append(var)
    for var_list in courses.values():
        model.Add(sum(var_list) <= 1)

# Constraint: each student gets exactly 8 assigned courses (8 periods)
for s_name in student_course_map:
    model.Add(sum(var for _, _, var in student_course_map[s_name]) == MAX_PERIODS)

# Constraint: section size limits
for sec_id in sections:
    assigned_vars = [var for (s, sid), var in student_section_vars.items() if sid == sec_id]
    max_size = section_meta[sec_id]["max_students"]
    if assigned_vars:
        model.Add(sum(assigned_vars) <= max_size)

# Constraint: no student can take two classes in the same period
for s_name in student_course_map:
    for p in PERIODS:
        overlap_vars = []
        for course, sec_id, var in student_course_map[s_name]:
            if sec_id in section_period:
                # Create an indicator that activates when sec is in period p
                is_in_p = model.NewBoolVar(f"{s_name}_{sec_id}_p{p}")
                model.Add(section_period[sec_id] == p).OnlyEnforceIf(is_in_p)
                model.Add(section_period[sec_id] != p).OnlyEnforceIf(is_in_p.Not())
                overlap_vars.append((var, is_in_p))
        if overlap_vars:
            sum_vars = [model.NewBoolVar(f"overlap_{s_name}_{p}_{i}") for i in range(len(overlap_vars))]
            for i, (v, is_in_p) in enumerate(overlap_vars):
                model.AddBoolAnd([v, is_in_p]).OnlyEnforceIf(sum_vars[i])
                model.AddBoolOr([v.Not(), is_in_p.Not()]).OnlyEnforceIf(sum_vars[i].Not())
            model.Add(sum(sum_vars) <= 1)


# Enforce teacher max periods (off-period control from teachers.csv)
for t_idx, row in teachers_df.iterrows():
    max_periods = int(row["max_periods"])
    assigned_sections = []
    for sec_id in sections:
        if sec_id not in section_teacher:
            continue
        is_assigned = model.NewBoolVar(f"{sec_id}_t{t_idx}")
        model.Add(section_teacher[sec_id] == t_idx).OnlyEnforceIf(is_assigned)
        model.Add(section_teacher[sec_id] != t_idx).OnlyEnforceIf(is_assigned.Not())
        assigned_sections.append(is_assigned)
    model.Add(sum(assigned_sections) <= max_periods)



# Student-section enrollment variables
student_section_vars = {}
student_course_map = defaultdict(list)

for _, student in students_df.iterrows():
    s_name = student["name"]
    s_grade = str(student["grade"])
    required = student["required_courses"].split(";")
    electives = student["elective_choices"].split(";")
    bibles = student["bible_choices"].split(";")

    # Take top 4 electives and top 4 bible choices
    all_courses = set(required)
    all_courses.update(electives[:4])
    all_courses.update(bibles[:4])

    for sec_id in sections:
        course = section_meta[sec_id]["course"]
        if course in all_courses:
            var = model.NewBoolVar(f"{s_name}_{sec_id}")
            student_section_vars[(s_name, sec_id)] = var
            student_course_map[s_name].append((course, sec_id, var))


print("\nStudent section availability:")
for _, student in students_df.iterrows():
    s_name = student["name"]
    assigned = [sec_id for (name, sec_id), var in student_section_vars.items() if name == s_name]
    print(f"  {s_name}: can enroll in {len(assigned)} sections")


# Ensure one section per course per student
for s_name in student_course_map:
    course_vars = defaultdict(list)
    for course, sec_id, var in student_course_map[s_name]:
        course_vars[course].append(var)
    for vars_for_course in course_vars.values():
        model.Add(sum(vars_for_course) <= 1)

# Student should be assigned between 5 and 8 total classes
for s_name in student_course_map:
    model.Add(sum(var for _, _, var in student_course_map[s_name]) >= 5)
    model.Add(sum(var for _, _, var in student_course_map[s_name]) <= 8)

# No overlapping classes per student in the same period
for s_name in student_course_map:
    for p in PERIODS:
        overlap_vars = []
        for course, sec_id, var in student_course_map[s_name]:
            is_in_period = model.NewBoolVar(f"{s_name}_{sec_id}_p{p}")
            model.Add(section_period[sec_id] == p).OnlyEnforceIf(is_in_period)
            model.Add(section_period[sec_id] != p).OnlyEnforceIf(is_in_period.Not())
            both_active = model.NewBoolVar(f"both_{s_name}_{sec_id}_p{p}")
            model.AddBoolAnd([var, is_in_period]).OnlyEnforceIf(both_active)
            model.AddBoolOr([var.Not(), is_in_period.Not()]).OnlyEnforceIf(both_active.Not())
            overlap_vars.append(both_active)
        model.Add(sum(overlap_vars) <= 1)

# Debug: Print number of students requesting each course
from collections import Counter
course_counter = Counter()
for v in student_course_map.values():
    unique_courses = set(course for course, _, _ in v)
    course_counter.update(unique_courses)

print("Course request counts (unique students per course):")
for course, count in course_counter.items():
    print(f"  {course}: {count} students")


# Build model object
solver = cp_model.CpSolver()
solver.parameters.search_branching = cp_model.FIXED_SEARCH
solver.parameters.max_time_in_seconds = 300.0
solver.parameters.log_search_progress = True

status = solver.Solve(model)

if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    print("Schedule created successfully.")
    # Export final schedule to CSV
    import csv

    with open("./final_schedule.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Student", "Section", "Course", "Period"])
        for (s_name, sec_id), var in student_section_vars.items():
            if solver.BooleanValue(var):
                period = solver.Value(section_period[sec_id])
                course = section_meta[sec_id]["course"]
                writer.writerow([s_name, sec_id, course, period])
    print("Final schedule exported to final_schedule.csv.")
    # Export teacher and room assignments per section
    with open("./section_assignments.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Section", "Course", "Period", "Room", "Teacher"])
        for sec_id in sections:
            period = solver.Value(section_period[sec_id])
            room_idx = solver.Value(section_room[sec_id])
            teacher_idx = solver.Value(section_teacher[sec_id])
            room_name = rooms_df.iloc[room_idx]["room"]
            teacher_name = teachers_df.iloc[teacher_idx]["name"]
            course = section_meta[sec_id]["course"]
            writer.writerow([sec_id, course, period, room_name, teacher_name])
    print("Section assignments exported to section_assignments.csv.")


else:
    print("No valid schedule found within time limit.")