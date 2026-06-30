import random
import re

# Cebu-localized synthetic names pools
FIRST_NAMES_MALE = [
    "Juan Miguel", "Jose Mari", "Mark Gil", "Junjun", "Dexter", "John Paul", "Carlo", "Ramon", 
    "Kenneth", "Christian", "Reynaldo", "Alvin", "Michael", "Francis", "Jomar", "Sherwin", 
    "Edgardo", "Melvin", "Gerald", "Jerome", "Rogelio", "Santi", "Dante", "Elmer", "Gabriel"
]

FIRST_NAMES_FEMALE = [
    "Maria Clara", "Rhea Mae", "Angelica", "Mary Joy", "Kassandra", "Christine", "Sarah", "Jonalyn", 
    "Michelle", "Princess", "Cherry", "Gwendolyn", "Irish", "Kimberly", "Lovely", "Rachelle", 
    "Shiela", "Analyn", "Bernadette", "Glenda", "Jocelyn", "Katrina", "Patricia", "Liezel", "Therese"
]

LAST_NAMES = [
    "Dela Cruz", "Santos", "Buot", "Bacalso", "Fernandez", "Alcantara", "Cabahug", "Ceniza", 
    "Abella", "Gomez", "Ramos", "Bontuyan", "Villaver", "Suarez", "Tagalog", "Ondoy", 
    "Chan", "Lim", "Go", "Ybañez", "Villamor", "Quisumbing", "Arong", "Ruiz", "Gonzales"
]

CEBU_LOCATIONS = [
    "Cebu City", "Lapu-Lapu City", "Mandaue City", "Talisay City", "Consolacion", 
    "Minglanilla", "Cordova", "Carcar City", "Danao City", "Toledo City"
]

COURSES = [
    "BS Information Technology", "BS Computer Science", "BS Business Administration", 
    "BS Hospitality Management", "BS Civil Engineering", "BS Nursing", "AB Communication"
]

SCHOOLS = [
    "University of Cebu", "University of San Carlos", "Cebu Institute of Technology - University", 
    "University of San Jose - Recoletos", "University of the Visayas", "Indiana Aerospace University", 
    "Cebu Technological University"
]

SECTIONS = [
    "A", "B", "C", "D", "1A", "2B", "3A", "4A", "IT-3A", "CS-2B", "BA-1C"
]

def generate_synthetic_record(scanned_questions):
    """Generates a single synthetic record mapping scanned questions to varied, 
    consistent, Cebu-localized, fictional answers.
    """
    record = {}
    
    # 1. Establish demographic base for profile consistency
    gender = random.choice(["Male", "Female"])
    first_name = random.choice(FIRST_NAMES_MALE) if gender == "Male" else random.choice(FIRST_NAMES_FEMALE)
    last_name = random.choice(LAST_NAMES)
    middle_initial = random.choice(["A.", "B.", "C.", "D.", "E.", "M.", "P.", "S.", "T.", "V."])
    
    # Fictional Name formatting
    full_name = f"{last_name}, {first_name} {middle_initial}"
    email_user = f"{first_name.lower().replace(' ', '.')}.{last_name.lower().replace(' ', '')}.test"
    email = f"{email_user}@example.com"
    
    # Select location, school, course
    location = random.choice(CEBU_LOCATIONS)
    school = random.choice(SCHOOLS)
    course = random.choice(COURSES)
    
    # Extract short course prefix for section name
    course_prefix = "GEN"
    if "information technology" in course.lower():
        course_prefix = "IT"
    elif "computer science" in course.lower():
        course_prefix = "CS"
    elif "business" in course.lower():
        course_prefix = "BA"
    elif "civil" in course.lower():
        course_prefix = "CE"
    elif "nursing" in course.lower():
        course_prefix = "NS"
        
    year_level = random.choice(["1", "2", "3", "4"])
    section = f"{course_prefix}-{year_level}{random.choice(['A', 'B', 'C'])}"
    
    # 2. Map answers based on actual scanned fields
    for q in scanned_questions:
        label = q["label"]
        label_lower = label.lower()
        q_type = q["type"]
        options = q.get("options", [])
        
        # If the question is option-based, we MUST choose from the actual options
        if q_type in ["multiple_choice", "dropdown", "checkbox"] and options:
            # Handle specific known option-based questions
            if "gender" in label_lower or "sex" in label_lower:
                # Try to match profile gender
                matched = None
                for opt in options:
                    if gender.lower() in opt.lower():
                        matched = opt
                        break
                record[label] = matched if matched else options[0]
                
            elif "age" in label_lower:
                if len(options) > 1:
                    record[label] = random.choice(options)
                else:
                    record[label] = options[0]
                    
            elif "strand" in label_lower or "shs" in label_lower:
                record[label] = random.choice(options)
                
            elif "gpa" in label_lower or "grade" in label_lower or "average" in label_lower:
                record[label] = random.choice(options)
                
            elif is_likert_scale(options):
                record[label] = choose_likert_answer(options)
                
            elif is_numeric_scale(options):
                record[label] = random.choice(options)
                
            else:
                if q_type == "checkbox":
                    num_select = min(len(options), random.choice([1, 2]))
                    selected = random.sample(options, num_select)
                    record[label] = ", ".join(selected)
                else:
                    record[label] = random.choice(options)
                    
        else:
            # Free text / date / time questions
            if "email" in label_lower or "e-mail" in label_lower or "gmail" in label_lower:
                record[label] = email
            elif "name" in label_lower or "full name" in label_lower:
                record[label] = full_name
            elif "address" in label_lower or "location" in label_lower or "city" in label_lower:
                record[label] = f"{location}, Cebu"
            elif "school" in label_lower or "university" in label_lower or "college" in label_lower:
                record[label] = school
            elif "course" in label_lower or "program" in label_lower:
                record[label] = course
            elif "section" in label_lower or "class" in label_lower:
                record[label] = section
            elif "age" in label_lower:
                record[label] = str(random.randint(18, 25))
            elif "phone" in label_lower or "mobile" in label_lower or "contact" in label_lower:
                record[label] = f"0917{random.randint(1000000, 9999999)}"
            elif "student id" in label_lower or "id number" in label_lower or "student no" in label_lower:
                record[label] = f"202{random.randint(1,4)}00{random.randint(100, 999)}"
            elif q_type == "date":
                record[label] = f"2026-07-0{random.randint(1, 9)}"
            elif q_type == "time":
                record[label] = f"{random.randint(8, 17)}:00"
            else:
                record[label] = "Fictional response for system testing."
                
    return record

def is_likert_scale(options):
    """Helper to detect if options represent a Likert agreement scale."""
    likert_keywords = ["agree", "disagree", "neutral", "strongly", "satisfy", "dissatisfy", "never", "always"]
    match_count = 0
    for opt in options:
        opt_lower = opt.lower()
        if any(kw in opt_lower for kw in likert_keywords):
            match_count += 1
    return match_count >= 2

def choose_likert_answer(options):
    """Applies a realistic weighted distribution to select a Likert answer."""
    weights = []
    
    for opt in options:
        opt_lower = opt.lower()
        if "strongly agree" in opt_lower or "always" in opt_lower or "strongly satisfy" in opt_lower:
            weights.append(0.20)
        elif "agree" in opt_lower or "often" in opt_lower or "satisfy" in opt_lower:
            weights.append(0.35)
        elif "neutral" in opt_lower or "sometimes" in opt_lower or "undecided" in opt_lower:
            weights.append(0.25)
        elif "disagree" in opt_lower or "seldom" in opt_lower or "dissatisfy" in opt_lower:
            weights.append(0.15)
        elif "strongly disagree" in opt_lower or "never" in opt_lower or "strongly dissatisfy" in opt_lower:
            weights.append(0.05)
        else:
            weights.append(0.20)
            
    total_w = sum(weights)
    if total_w > 0:
        weights = [w / total_w for w in weights]
    else:
        weights = [1.0 / len(options)] * len(options)
        
    return random.choices(options, weights=weights, k=1)[0]

def is_numeric_scale(options):
    """Helper to detect if options represent a numeric scale (e.g. 1 to 5)."""
    return all(re.match(r'^\d+$', opt.strip()) for opt in options if opt.strip())

def generate_batch_synthetic_data(scanned_questions, count):
    """Generates multiple synthetic records split by '---'."""
    records = []
    for _ in range(count):
        rec = generate_synthetic_record(scanned_questions)
        lines = []
        for k, v in rec.items():
            lines.append(f"{k}: {v}")
        records.append("\n".join(lines))
        
    return "\n---\n".join(records)
