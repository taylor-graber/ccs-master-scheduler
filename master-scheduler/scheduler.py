import csv
import re
from collections import defaultdict
from pathlib import Path
from pdfminer.high_level import extract_text

# --- File Paths ---
BASE_DIR = Path(__file__).parent / "data"
PDF_PATH = BASE_DIR / "requests.pdf"
STUDENTS_CSV = BASE_DIR / "students.csv"
COURSES_CSV = BASE_DIR / "courses.csv"

# --- Constants ---
TOTAL_PERIODS = 8
MAX_CLASS_SIZE = 20
REQUIRED_CATEGORIES = ["English", "Math", "Science", "History"]

# --- Step 1: Load Course Categories ---
def load_course_categories():
    course_categories = {}
    with open(COURSES_CSV, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            course_categories[row['name'].strip()] = row['category'].strip()
    return course_categories

# --- Step 2: Parse PDF Data ---
def is_probable_name(line: str, course_names: set = None) -> bool:
    """Check if a line looks like a student's name."""
    parts = line.strip().split()
    if len(parts) != 2:
        return False
    if course_names and line in course_names:
        return False
    first, last = parts
    return first.istitle() and last.istitle() and first.isalpha() and last.isalpha()

def load_course_categories(csv_path):
    course_categories = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name'].strip()
            category = row['category'].strip()
            course_categories[name] = category
    return course_categories

def is_likely_name(line):
    return bool(re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', line.strip()))


def extract_student_requests_from_lines(pdf_path, course_categories):
    lines = extract_text(pdf_path).splitlines()
    students = []
    current_student = None
    current_courses = []

    category_prefixes = ["Math", "Science", "English", "History", "Foreign Language", "Elective", "Bible"]

    def is_student_line(line):
        # A line with 2+ capitalized words, no category prefix, not a request line
        return (
            len(line.split()) == 2 and
            all(word.istitle() for word in line.split()) and
            not any(line.startswith(prefix) for prefix in category_prefixes) and
            "Request" not in line
        )

    def add_student():
        if current_student and current_student['name'] and current_courses:
            categorized = {
                "required_courses": [],
                "elective": [],
                "bible": [],
                "studyhall": []
            }
            for course in current_courses:
                category = course_categories.get(course.strip(), "")
                if category == "Elective":
                    categorized["elective"].append(course)
                elif category == "Bible":
                    categorized["bible"].append(course)
                elif category == "StudyHall":
                    categorized["studyhall"].append(course)
                else:
                    categorized["required_courses"].append(course)

            students.append({
                "name": current_student["name"],
                "grade": current_student["grade"],
                "required_courses": ";".join(categorized["required_courses"]),
                "elective_choice_1": categorized["elective"][0] if len(categorized["elective"]) > 0 else "",
                "elective_choice_2": categorized["elective"][1] if len(categorized["elective"]) > 1 else "",
                "elective_choice_3": categorized["elective"][2] if len(categorized["elective"]) > 2 else "",
                "elective_choice_4": categorized["elective"][3] if len(categorized["elective"]) > 3 else "",
                "bible_choice_1": categorized["bible"][0] if len(categorized["bible"]) > 0 else "",
                "bible_choice_2": categorized["bible"][1] if len(categorized["bible"]) > 1 else "",
                "bible_choice_3": categorized["bible"][2] if len(categorized["bible"]) > 2 else "",
                "bible_choice_4": categorized["bible"][3] if len(categorized["bible"]) > 3 else "",
            })

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if is_student_line(line):
            add_student()
            current_student = {
                "name": line,
                "grade": "10"  # Hardcoded grade for now
            }
            current_courses = []
        elif line.startswith("School Given Request"):
            course = line.replace("School Given Request", "").strip()
            current_courses.append(course)
        elif any(line.startswith(prefix) for prefix in category_prefixes):
            parts = line.split()
            course = " ".join(parts[1:]).strip()
            current_courses.append(course)

    add_student()
    return students





# --- Step 3: Save to students.csv ---
def save_students_csv(students):
    fields = ["name", "grade", "required_courses", "elective_choice_1", "elective_choice_2", "elective_choice_3", "elective_choice_4",
              "bible_choice_1", "bible_choice_2", "bible_choice_3", "bible_choice_4"]
    with open(STUDENTS_CSV, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for student in students:
            row = {
                "name": student["name"],
                "grade": student["grade"],
                "required_courses": ",".join(student["required_courses"]),
            }
            for i in range(4):
                row[f"elective_choice_{i+1}"] = student.get(f"elective_choice_{i+1}", "")
                row[f"bible_choice_{i+1}"] = student.get(f"bible_choice_{i+1}", "")
            writer.writerow(row)

# --- Step 4: Import Students from CSV ---
def import_students(filename=STUDENTS_CSV):
    students = []
    with open(filename, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            required_courses = row['required_courses'].split(',')
            electives = [row[f'elective_choice_{i}'] for i in range(1, 5) if row.get(f'elective_choice_{i}', '') != '']
            bible_choices = [row[f'bible_choice_{i}'] for i in range(1, 5) if row.get(f'bible_choice_{i}', '') != '']
            students.append({
                'name': row['name'],
                'grade': int(row['grade']),
                'required_courses': required_courses,
                'elective_choices': electives,
                'bible_choices': bible_choices
            })
    return students

# --- Update Course Count ---
def update_course_counts(course_csv_path, students):
    # Count how many students selected each course
    course_student_counts = defaultdict(int)
    for student in students:
        all_courses = (
            student["required_courses"]
            + student["elective_choices"]
            + student["bible_choices"]
        )
        for course in all_courses:
            course_student_counts[course] += 1

    # Read course names from courses.csv
    updated_rows = []
    with open(course_csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        updated_rows.append(header)

        valid_course_names = set()
        for row in reader:
            course_name = row[0]
            valid_course_names.add(course_name)
            student_count = str(course_student_counts.get(course_name, 0))
            row[2] = student_count  # Update the third column: students
            updated_rows.append(row)

    # Write updated rows back to CSV
    with open(course_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(updated_rows)

    # Log unmatched course names
    unmatched_courses = set(course_student_counts.keys()) - valid_course_names
    if unmatched_courses:
        print("Unmatched course names in student requests not found in courses.csv:")
        for name in sorted(unmatched_courses):
            print(f"  - {name}")
    else:
        print("All course names matched successfully.")

# --- Step 5: Import Courses, Teachers, and Rooms ---
def import_courses():
    courses = {}
    with open(COURSES_CSV, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            manual_sections = row.get('sections')
            courses[row['name']] = {
                "room_type": row['room_type'],
                "students": int(row['students']),
                "manual_sections": int(manual_sections) if manual_sections and manual_sections.isdigit() else None,
                "category": row['category'].strip()
            }
    return courses

def import_teachers():
    teachers = {}
    with open(BASE_DIR / "teachers.csv", mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            teachers[row['name']] = {
                "courses": row['courses'].split(','),
                "availability": list(map(int, row['availability'].split(','))),
                "off_periods_required": int(row.get('required_off_periods', 1)),
                "preferred_room": row.get('preferred_room', None),
                "assigned_periods": []
            }
    return teachers

def import_rooms():
    rooms = {}
    with open(BASE_DIR / "rooms.csv", mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            rooms[row['name']] = {
                "type": row['type'],
                "availability": list(map(int, row['availability'].split(',')))
            }
    return rooms

# --- Step 6: Generate Schedule ---
def generate_schedule(teachers, rooms, courses, students, max_class_size=MAX_CLASS_SIZE):
    course_sections = {}
    teacher_room_preference = {teacher: None for teacher in teachers}

    # Create course sections
    for course, info in courses.items():
        num_sections = info["manual_sections"] if info["manual_sections"] is not None else \
                       (info["students"] + max_class_size - 1) // max_class_size
        course_sections[course] = []

        for _ in range(num_sections):
            section_assigned = False
            for teacher, t_info in teachers.items():
                if course not in t_info["courses"]:
                    continue

                max_periods = TOTAL_PERIODS - t_info["off_periods_required"]
                if len(t_info["assigned_periods"]) >= max_periods:
                    continue

                for period in t_info["availability"]:
                    if period in t_info["assigned_periods"]:
                        continue

                    # Try to keep the teacher in the same room if possible
                    preferred_room = t_info.get("preferred_room")  # Get the teacher's preferred room
                    room_assigned = False

                    if preferred_room and preferred_room in rooms:
                        # Try assigning the teacher to their preferred room
                        r_info = rooms[preferred_room]
                        if r_info["type"] == info["room_type"] and period in r_info["availability"]:
                            course_sections[course].append({
                                "course": course,
                                "teacher": teacher,
                                "period": period,
                                "room": preferred_room,
                                "students": []
                            })
                            t_info["assigned_periods"].append(period)
                            r_info["availability"].remove(period)
                            room_assigned = True
                            section_assigned = True
                            break

                    if not room_assigned:
                        # Try other rooms if the teacher doesn’t have a preferred room or it’s unavailable
                        for room, r_info in rooms.items():
                            if r_info["type"] == info["room_type"] and period in r_info["availability"]:
                                course_sections[course].append({
                                    "course": course,
                                    "teacher": teacher,
                                    "period": period,
                                    "room": room,
                                    "students": []
                                })
                                t_info["assigned_periods"].append(period)
                                r_info["availability"].remove(period)
                                section_assigned = True
                                if not teacher_room_preference[teacher]:
                                    teacher_room_preference[teacher] = room
                                break
                    if section_assigned:
                        break
                if section_assigned:
                    break
            if not section_assigned:
                print(f"Warning: Could not assign section for {course}")

    # Initialize tracking
    student_course_counts = {s['name']: 0 for s in students}
    student_categories = {s['name']: set() for s in students}

    # Sort students by grade
    students = sorted(students, key=lambda s: -s['grade'])

    def assign_student(course_name, student_name):
        for section in course_sections.get(course_name, []):
            if len(section["students"]) < max_class_size:
                section["students"].append(student_name)
                student_course_counts[student_name] += 1
                student_categories[student_name].add(courses[course_name]["category"])
                return True
        return False

    # Assign required courses
    for student in students:
        assigned = set()
        for course in student['required_courses']:
            if assign_student(course, student['name']):
                assigned.add(course)
        for category in REQUIRED_CATEGORIES:
            if category not in student_categories[student['name']]:
                for cname, cinfo in courses.items():
                    if cinfo['category'] == category and cname not in assigned:
                        if assign_student(cname, student['name']):
                            break

    # Assign bible
    for student in students:
        for bible in student['bible_choices']:
            if student_course_counts[student['name']] >= TOTAL_PERIODS:
                break
            if assign_student(bible, student['name']):
                break

    # Assign electives
    for student in students:
        for elective in student['elective_choices']:
            if student_course_counts[student['name']] >= TOTAL_PERIODS:
                break
            assign_student(elective, student['name'])

    # Fill with Study Hall
    for student in students:
        while student_course_counts[student['name']] < TOTAL_PERIODS:
            if not assign_student("Study Hall", student['name']):
                print(f"Warning: {student['name']} could not be fully scheduled.")
                break

    # Build final schedule
    final_schedule = []
    for sections in course_sections.values():
        for section in sections:
            for student in section["students"]:
                final_schedule.append({
                    "course": section["course"],
                    "teacher": section["teacher"],
                    "period": section["period"],
                    "room": section["room"],
                    "student": student,
                    "category": courses[section["course"]]["category"]
                })

    return final_schedule

def export_schedule(schedule, filename= BASE_DIR / "output_schedule.csv"):
    import csv
    with open(filename, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=["course", "teacher", "period", "room", "student", "category"])
        writer.writeheader()
        for row in schedule:
            writer.writerow(row)

def summarize_schedule(schedule, students, courses, teachers, rooms):
    print("Schedule Summary:")
    print(f"Students: {len(students)}")
    print(f"Courses: {len(courses)}")
    print(f"Teachers: {len(teachers)}")
    print(f"Rooms: {len(rooms)}")

# --- Main Execution ---
if __name__ == "__main__":
    BASE_DIR.mkdir(exist_ok=True)
    course_categories = load_course_categories(COURSES_CSV)
    student_data = extract_student_requests_from_lines(PDF_PATH, course_categories)
    save_students_csv(student_data)

    students = import_students()
    update_course_counts(COURSES_CSV, students)
    courses = import_courses()
    teachers = import_teachers()
    rooms = import_rooms()

    schedule = generate_schedule(teachers, rooms, courses, students)
    export_schedule(schedule)
    summarize_schedule(schedule, students, courses, teachers, rooms)