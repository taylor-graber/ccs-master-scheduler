from constraint import Problem, AllDifferentConstraint
from teacher_courses import teacher_courses
from section_period_options import section_period_options
from teacher_rooms import teacher_rooms
from course_sections import course_sections
import csv
from time import time

# Example student preferences
students = {
    "Alice": {
        "grade": 12,
        "required": {
            "Math": "Algebra II",
            "Science": "Biology",
            "History": "World History",
            "English": "English 10",
            "Bible": None
        },
        "electives": ["Art", "Music", "PE"]
    },
    "Bob": {
        "grade": 11,
        "required": {
            "Math": "Geometry",
            "Science": "Chemistry",
            "History": "World History",
            "English": "English 10",
            "Bible": None
        },
        "electives": ["Music", "Art", "PE"]
    },
    "Charlie": {
        "grade": 10,
        "required": {
            "Math": "Geometry",
            "Science": "Biology",
            "History": "World History",
            "English": "English 10",
            "Bible": None
        },
        "electives": ["PE", "Art", "Music"]
    }
}

bible_options = ["Bible I", "Bible II"]
elective_options = ["Art", "Music", "PE", "Study Hall"]
sorted_students = sorted(students.items(), key=lambda x: -x[1]["grade"])

problem = Problem()
sections = []

for course, max_sections in course_sections.items():
    for i in range(1, max_sections + 1):
        sections.append(f"{course}_Sec{i}")

section_period_map = {}
for section in sections:
    course = section.split("_Sec")[0]
    section_period_map[section] = section_period_options.get(course, [])

# Add variables for section period assignment
for section in sections:
    available_periods = section_period_map.get(section, [])
    if available_periods:
        problem.addVariable(f"{section}_period", available_periods)

# Assign student section variables
student_vars_map = {}
for student, prefs in sorted_students:
    required_courses = [c for c in prefs["required"].values() if c]

    if not prefs["required"].get("Bible"):
        for bible in bible_options:
            if bible in section_period_options:
                prefs["required"]["Bible"] = bible
                required_courses.append(bible)
                break

    electives_assigned = 0
    for elective in prefs["electives"]:
        if electives_assigned >= 2:
            break
        if elective in section_period_options and course_sections.get(elective, 0) > 0:
            required_courses.append(elective)
            electives_assigned += 1

    while len(required_courses) < 8:
        required_courses.append("Study Hall")

    student_vars = []
    for course in required_courses:
        var = f"{student}_{course}"
        options = [sec for sec in sections if sec.startswith(course)]
        if not options:
            print(f"⚠️ No valid options for {var} (course: {course}) — skipping.")
            continue
        problem.addVariable(var, options)
        student_vars.append(var)

    student_vars_map[student] = student_vars

# Student schedule constraint: all courses in different periods
def no_period_conflicts(*assigned_sections):
    used_periods = set()
    for sec in assigned_sections:
        period_var = f"{sec}_period"
        period = solution.get(period_var)
        if period in used_periods:
            return False
        used_periods.add(period)
    return True

# Add deferred constraint that accesses `solution`
def make_student_constraint(student_vars):
    def constraint(*assigned_sections):
        used = set()
        for sec in assigned_sections:
            p = solution.get(f"{sec}_period")
            if p is None or p in used:
                return False
            used.add(p)
        return True
    return constraint

# Class size limits
max_class_size = 18
section_capacity = {s: 0 for s in sections}

# Solve
start = time()
solutions = problem.getSolutions()
end = time()
print(f"Solving took {end - start:.2f} seconds")
valid_solutions = []

for sol in solutions:
    section_counts = {s: 0 for s in sections}
    for student, vars_ in student_vars_map.items():
        for var in vars_:
            sec = sol.get(var)
            if sec:
                section_counts[sec] += 1
    if all(v <= max_class_size for v in section_counts.values()):
        global solution
        solution = sol  # needed for dynamic period access
        valid = True
        for student, vars_ in student_vars_map.items():
            if not make_student_constraint(vars_)(*map(sol.get, vars_)):
                valid = False
                break
        if valid:
            valid_solutions.append(sol)

print(f"Found {len(valid_solutions)} valid solution(s).")

if valid_solutions:
    best = valid_solutions[0]
    print("\nAssigned Student Sections with Periods:")
    for student, prefs in sorted_students:
        print(f"\n{student}:")
        all_courses = [c for c in prefs["required"].values() if c]
        all_courses += prefs["electives"]
        for course in all_courses:
            var = f"{student}_{course}"
            section = best.get(var)
            period = best.get(f"{section}_period") if section else None
            if section:
                print(f"  {course}: {section} (Period {period})")

    # Export to CSV
    with open("student_schedule.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Student", "Course", "Section", "Period"])
        for student, prefs in sorted_students:
            all_courses = [c for c in prefs["required"].values() if c]
            all_courses += prefs["electives"]
            for course in all_courses:
                var = f"{student}_{course}"
                section = best.get(var)
                period = best.get(f"{section}_period") if section else None
                if section:
                    writer.writerow([student, course, section, period])
else:
    print("❌ No valid solution under class size limits.")


# 1. Visual grid: 8-period schedule for each student
student_periods = {student: [""] * 8 for student in students}
for student, prefs in sorted_students:
    all_courses = [c for c in prefs["required"].values() if c]
    all_courses += prefs["electives"]
    for course in all_courses:
        var = f"{student}_{course}"
        section = best.get(var)
        period = best.get(f"{section}_period") if section else None
        if section and period:
            student_periods[student][period - 1] = course

with open("student_schedule_grid.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Student"] + [f"Period {i}" for i in range(1, 9)])
    for student, periods in student_periods.items():
        writer.writerow([student] + periods)

# 2. Class rosters
rosters = {section: [] for section in sections}
for student, prefs in sorted_students:
    all_courses = [c for c in prefs["required"].values() if c]
    all_courses += prefs["electives"]
    for course in all_courses:
        var = f"{student}_{course}"
        section = best.get(var)
        if section:
            rosters[section].append(student)

with open("class_rosters.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Section", "Students"])
    for section, student_list in rosters.items():
        writer.writerow([section, ", ".join(student_list)])

# 3. Teacher & room assignments with preference matching
section_teacher_room = {}
teacher_room_counts = {teacher: {} for teacher in teacher_courses}
section_period_assignments = {s: best.get(f"{s}_period") for s in sections}

for teacher, courses in teacher_courses.items():
    assigned_courses = [c for c in courses if any(s.startswith(c) for s in sections)]
    for course in assigned_courses:
        for s in sections:
            if s.startswith(course) and s not in section_teacher_room:
                room_pref = teacher_rooms.get(teacher)
                section_teacher_room[s] = (teacher, room_pref)
                if room_pref:
                    teacher_room_counts[teacher][room_pref] = teacher_room_counts[teacher].get(room_pref, 0) + 1
                break

with open("section_assignments.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Section", "Period", "Teacher", "Room"])
    for section, (teacher, room) in section_teacher_room.items():
        period = section_period_assignments.get(section)
        writer.writerow([section, period, teacher, room])