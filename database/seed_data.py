import sqlite3
import json
import os
from datetime import datetime, timedelta

def seed():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'interntrack.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    benchmark_students = [
        ("1KG21CS045", "Rahul Kumar", "CSE", 8, "rahul.k@kletech.ac.in", "+91 9876543210", 8.5, 0, 112,
         json.dumps(["Python", "Machine Learning", "PyTorch", "FastAPI", "React"]),
         json.dumps(["AI/ML", "Data Science", "Backend Development"]),
         json.dumps(["Bangalore", "Hyderabad"]),
         "NOT_PLACED", None, None, None, now_str, now_str),
    
        ("1KG21CS008", "Ananya Sharma", "CSE", 8, "ananya.s@kletech.ac.in", "+91 9876543211", 9.1, 0, 118,
         json.dumps(["Java", "Spring Boot", "AWS", "Microservices", "Docker"]),
         json.dumps(["Cloud Engineering", "Enterprise Systems"]),
         json.dumps(["Bengaluru", "Pune"]),
         "PLACED_COMPANY", "TCS Digital", "Offered 7.5 LPA with 4-Month Integrated Internship", "2025-11-15", now_str, now_str),
    
        ("1KG21CS072", "Rohan Verma", "CSE", 8, "rohan.v@kletech.ac.in", "+91 9876543212", 7.2, 0, 104,
         json.dumps(["JavaScript", "React", "Node.js", "MongoDB", "TailwindCSS"]),
         json.dumps(["Full Stack Web Development"]),
         json.dumps(["Bangalore", "Remote"]),
         "NOT_PLACED", None, None, None, now_str, now_str),
    
        ("1KG21CS099", "Sneha Patil", "CSE", 8, "sneha.p@kletech.ac.in", "+91 9876543213", 6.8, 1, 98,
         json.dumps(["Python", "Software Testing", "Selenium", "SQL"]),
         json.dumps(["QA Engineering", "Database Administration"]),
         json.dumps(["Pune", "Bangalore"]),
         "NOT_PLACED", None, None, None, now_str, now_str),
    
        ("1KG21CS050", "Anam", "CSE", 8, "anam.k@kletech.ac.in", "+91 9876543214", 8.8, 0, 115,
         json.dumps(["Python", "Java", "Machine Learning", "Cloud Systems", "Data Structures"]),
         json.dumps(["Research & Innovation", "AI/ML", "Software Engineering"]),
         json.dumps(["Bengaluru", "Pune"]),
         "NOT_PLACED", None, None, None, now_str, now_str),
    ]
    
    # 2. Real-World Engineering Batch (KLE Tech / Hubballi Style Real Students)
    additional_students_data = [
        # USN, Name, Branch, CGPA, Backlogs, Placed Company, Package
        ("01FE21BCS001", "Aishwarya Patil", "CSE", 9.4, 0, "Microsoft India", "Offered 24 LPA Full-Time with Summer Internship"),
        ("01FE21BCS002", "Abhishek Kulkarni", "CSE", 8.9, 0, "Robert Bosch", "Offered 9.5 LPA R&D Systems Engineer"),
        ("01FE21BCS003", "Pooja Hegde", "ISE", 8.7, 0, "Infosys Limited", "Offered 6.5 LPA InStep Digital Specialist"),
        ("01FE21BCS004", "Mohammed Farhan", "CSE", 8.4, 0, "Amazon Web Services (AWS)", "Offered 18 LPA Cloud Associate"),
        ("01FE21BCS005", "Tanvi Deshpande", "AIML", 9.2, 0, "Google India", "Offered 28 LPA SWE Intern"),
        ("01FE21BCS006", "Karthik Hiremath", "CSE", 7.8, 0, "Cisco Systems India", "Offered 14 LPA Network Software Intern"),
        ("01FE21BCS007", "Priyanka Joshi", "CSE", 8.6, 0, "Goldman Sachs India", "Offered 22 LPA Quant Analyst Intern"),
        ("01FE21BCS008", "Sachin Kalghatgi", "CSE", 7.4, 0, "Accenture India", "Offered 6.5 LPA Advanced App Intern"),
        ("01FE21BCS009", "Shruti Bellad", "AIML", 8.8, 0, "Adobe Systems India", "Offered 20 LPA Creative Cloud Intern"),
        ("01FE21BCS010", "Aditya Nayak", "CSE", 8.1, 0, "Samsung R&D Institute (SRI-B)", "Offered 12 LPA On-Device AI Intern"),
        ("01FE21BCS011", "Keerthi Shastry", "ISE", 7.9, 0, "Flipkart India", "Offered 16 LPA E-Commerce Intern"),
        ("01FE21BCS012", "Vinayak Badiger", "CSE", 8.3, 0, "Oracle India", "Offered 11 LPA Cloud Database Intern"),
        ("01FE21BCS013", "Meghana Kulkarni", "AIML", 9.0, 0, "NVIDIA India", "Offered 26 LPA Deep Learning Intern"),
        ("01FE21BCS014", "Darshan Angadi", "CSE", 7.6, 0, "Wipro Limited", "Offered 6.0 LPA Turbo Developer"),
        ("01FE21BCS015", "Soumya Hunasimarad", "CSE", 8.2, 0, "Razorpay", "Offered 15 LPA FinTech Backend Intern"),
        ("01FE21BCS016", "Nikhil Chougule", "ISE", 8.0, 0, "Swiggy", "Offered 14 LPA Routing AI Intern"),
        ("01FE21BCS017", "Deepa Hosamani", "CSE", 7.7, 0, "Zoho Corporation", "Offered 8.5 LPA SaaS Developer"),
        ("01FE21BCS018", "Pranav Shirahatti", "AIML", 8.5, 0, "Intel Technology India", "Offered 13.5 LPA Silicon Systems Intern"),
        
        # Non-placed students applying through normal portal (Active Applications)
        ("01FE21BCS019", "Rakesh Goudar", "CSE", 8.1, 0, None, None),
        ("01FE21BCS020", "Shreya Hubballi", "CSE", 8.4, 0, None, None),
        ("01FE21BCS021", "Manjunath Byahatti", "CSE", 7.9, 0, None, None),
        ("01FE21BCS022", "Kavya Dharwadkar", "AIML", 8.6, 0, None, None),
        ("01FE21BCS023", "Basavaraj Patil", "CSE", 7.3, 0, None, None),
        ("01FE21BCS024", "Ankita Belagavi", "ISE", 8.2, 0, None, None),
        ("01FE21BCS025", "Guruprasad Joshi", "CSE", 7.5, 0, None, None),
        ("01FE21BCS026", "Laxmi Meti", "CSE", 8.0, 0, None, None),
        ("01FE21BCS027", "Mallikarjun Yaragatti", "AIML", 8.3, 0, None, None),
        ("01FE21BCS028", "Sneha Annigeri", "CSE", 7.7, 0, None, None),
        ("01FE21BCS029", "Naveen Kundagol", "CSE", 7.2, 0, None, None),
        ("01FE21BCS030", "Bhavana Navalgund", "ISE", 8.5, 0, None, None),
        ("01FE21BCS031", "Pradeep Kalburgi", "CSE", 7.8, 0, None, None),
        ("01FE21BCS032", "Roopa Ron", "CSE", 8.1, 0, None, None),
        ("01FE21BCS033", "Shivanand Gadag", "AIML", 8.7, 0, None, None),
        ("01FE21BCS034", "Vidya Mundargi", "CSE", 7.4, 0, None, None),
        ("01FE21BCS035", "Sunil Shirhatti", "CSE", 7.6, 0, None, None),
        ("01FE21BCS036", "Sangeeta Savanur", "ISE", 8.3, 0, None, None),
        ("01FE21BCS037", "Vijaykumar Haveri", "CSE", 7.9, 0, None, None),
        ("01FE21BCS038", "Sushma Ranebennur", "CSE", 8.0, 0, None, None),
        ("01FE21BCS039", "Praveen Byadgi", "AIML", 8.4, 0, None, None),
        ("01FE21BCS040", "Asha Hirekerur", "CSE", 7.1, 0, None, None),
        ("01FE21BCS041", "Raghavendra Hangal", "CSE", 7.5, 0, None, None),
        ("01FE21BCS042", "Geeta Shiggaon", "ISE", 8.2, 0, None, None),
        ("01FE21BCS043", "Anand Bankapur", "CSE", 7.8, 0, None, None),
        ("01FE21BCS044", "Netravati Karwar", "AIML", 8.6, 0, None, None),
        ("01FE21BCS045", "Suresh Ankola", "CSE", 7.3, 0, None, None),
        ("01FE21BCS046", "Radha Kumta", "CSE", 8.1, 0, None, None),
        ("01FE21BCS047", "Chetan Honnavar", "ISE", 7.7, 0, None, None),
        ("01FE21BCS048", "Archana Bhatkal", "CSE", 8.5, 0, None, None),
        ("01FE21BCS049", "Girish Sirsi", "AIML", 8.0, 0, None, None),
        ("01FE21BCS050", "Deepika Yellapur", "CSE", 7.6, 0, None, None),
        ("01FE21BCS051", "Santosh Dandeli", "CSE", 7.2, 0, None, None),
        ("01FE21BCS052", "Jyoti Haliyal", "ISE", 8.3, 0, None, None),
        ("01FE21BCS053", "Mahesh Mundgod", "CSE", 6.9, 1, None, None), # Academic caution with 1 backlog
        ("01FE21BCS054", "Renuka Joida", "AIML", 8.2, 0, None, None),
        ("01FE21BCS055", "Ashok Siddapur", "CSE", 7.5, 0, None, None),
        ("01FE21BCS056", "Vandana Gokak", "CSE", 8.4, 0, None, None),
        ("01FE21BCS057", "Kiran Athani", "ISE", 7.1, 0, None, None),
        ("01FE21BCS058", "Pallavi Chikodi", "CSE", 8.7, 0, None, None),
        ("01FE21BCS059", "Umesh Bailhongal", "AIML", 7.8, 0, None, None),
        ("01FE21BCS060", "Savita Saundatti", "CSE", 8.0, 0, None, None),
    ]
    
    all_students = []
    all_students.extend(benchmark_students)
    
    skills_pool = [
        ["Python", "FastAPI", "SQL", "Docker", "Git"],
        ["Java", "Spring Boot", "Microservices", "PostgreSQL", "Kafka"],
        ["React", "TypeScript", "Node.js", "MongoDB", "REST APIs"],
        ["Python", "PyTorch", "TensorFlow", "Computer Vision", "NLP"],
        ["C++", "Data Structures", "Algorithms", "Linux", "Multi-Threading"],
        ["Cloud Engineering", "AWS", "Terraform", "CI/CD", "Kubernetes"],
        ["Data Analytics", "Pandas", "PowerBI", "SQL", "Statistical Modeling"]
    ]
    
    for idx, item in enumerate(additional_students_data):
        usn, name, branch, cgpa, backlogs, placed_comp, pkg = item
        email = f"{name.lower().replace(' ', '.')}@kletech.ac.in"
        phone = f"+91 9845{idx+10:04d}0"
        sk = json.dumps(skills_pool[idx % len(skills_pool)])
        domains = json.dumps(["AI/ML", "Cloud Software", "Full Stack Development"])
        locs = json.dumps(["Bangalore", "Pune", "Hyderabad"])
        status = "PLACED_COMPANY" if placed_comp else "NOT_PLACED"
        credits = 100 + int((cgpa - 6.0) * 10)
        p_date = "2025-11-20" if placed_comp else None
        
        all_students.append((
            usn, name, branch, 8, email, phone, cgpa, backlogs, credits,
            sk, domains, locs, status, placed_comp, pkg, p_date, now_str, now_str
        ))
    
    # Clear old spam test submissions and student profiles
    cursor.execute("DELETE FROM student_profiles;")
    cursor.execute("DELETE FROM student_submissions;")
    cursor.execute("DELETE FROM internships;")
    cursor.execute("DELETE FROM progress_reports;")
    cursor.execute("DELETE FROM evaluations;")
    
    # Insert Students
    cursor.executemany("""
    INSERT INTO student_profiles (
        usn, name, branch, semester, email, phone, cgpa, backlogs, credits,
        skills, preferred_domains, preferred_locations,
        placement_status, placed_company, placement_details, placement_date,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_students)
    
    # Also ensure all students have user accounts for login
    user_rows = []
    for s in all_students:
        usn = s[0]
        name = s[1]
        email = s[4]
        uid = f"USR-{usn}"
        user_rows.append((uid, email, "student123", "STUDENT", usn, name, 1, now_str))
    
    # Add coordinator and HOD
    user_rows.append(("USR-COORD", "coordinator@kletech.ac.in", "coord123", "COORDINATOR", None, "Dr. Ramesh Kulkarni (Internship Coordinator)", 1, now_str))
    user_rows.append(("USR-HOD", "hod.cse@kletech.ac.in", "hod123", "HOD", None, "Prof. Sunita Deshmukh (Head of Department)", 1, now_str))
    
    cursor.execute("DELETE FROM users;")
    cursor.executemany("""
    INSERT OR REPLACE INTO users (id, email, password_hash, role, usn, full_name, is_active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, user_rows)
    
    approved_companies_pool = [
        ("Tata Consultancy Services (TCS)", "Research & Innovation Intern", "Bangalore", "Sanjay Mehta (TCS Senior Lead)"),
        ("Infosys Limited", "InStep Software Development Intern", "Bangalore", "Rajesh Nair (Infosys Principal Architect)"),
        ("Robert Bosch", "AI/ML & Embedded Systems Intern", "Bangalore", "Dr. Rajesh Kulkarni (Bosch Tech Director)"),
        ("Google India", "Software Engineering Summer Intern", "Bangalore", "Arun V (Google Senior SWE)"),
        ("Microsoft India", "Software Development Intern", "Bengaluru", "Priya Nair (Microsoft Principal Eng)"),
        ("Amazon Web Services (AWS)", "Cloud Solutions Architecture Intern", "Bangalore", "Vikram Sen (AWS Solutions Lead)"),
        ("Cisco Systems India", "Network Software Engineering Intern", "Bangalore", "Amitabh Sen (Cisco Director)"),
        ("Adobe Systems India", "Creative Cloud Software Intern", "Bangalore", "Neha Gupta (Adobe Staff Scientist)"),
        ("Goldman Sachs India", "Quantitative & Financial Systems Intern", "Bangalore", "Kunal Mehra (Goldman VP Engineering)"),
        ("Samsung R&D Institute (SRI-B)", "AI Vision & Mobile Systems Intern", "Bangalore", "Dr. H.S. Rao (Samsung Lead ML)"),
        ("Intel Technology India", "System Software & Silicon Intern", "Bangalore", "Manoj K (Intel Chief Architect)"),
        ("Oracle India", "Database & Cloud Infrastructure Intern", "Bangalore", "Deepak Roy (Oracle Director)"),
        ("Flipkart India", "E-Commerce Backend & Search Intern", "Bangalore", "Sunil Narang (Flipkart Tech Lead)"),
        ("Razorpay", "Fintech Backend & Payments Intern", "Bangalore", "Gaurav S (Razorpay Architect)"),
        ("Swiggy", "Logistics & Routing AI Intern", "Bangalore", "Rohit Joshi (Swiggy VP AI)"),
        ("Zoho Corporation", "Full Stack Product Developer Intern", "Bangalore", "Venkatesh S (Zoho Product Head)"),
        ("ABC Technologies", "AI/ML Intern", "Bangalore", "Dr. Anand Kumar (AI Director)"),
        ("Accenture India", "Advanced Technology & Cloud Intern", "Bangalore", "Suresh G (Accenture Lead)")
    ]
    
    submissions = []
    internships = []
    progress_reports = []
    evaluations = []
    
    for idx, s in enumerate(all_students):
        usn = s[0]
        name = s[1]
        cgpa = s[6]
        backlogs = s[7]
        placement_status = s[12]
        placed_comp = s[13]
        placed_pkg = s[14]
    
        sub_id = f"SUB-2026-{idx+1:03d}"
        
        # 1. Placed Company Stream (19 Students)
        if placement_status == "PLACED_COMPANY":
            submissions.append((
                sub_id, usn, 1, "PLACED_COMPANY",
                placed_comp, placed_pkg, "4 Months",
                None, None, None, None,
                "CONFIRMED", "APPROVED", "Campus placement internship confirmed directly by Placement Cell.",
                placed_comp, "Software Engineering Intern", "4 Months",
                "Dr. Ramesh Kulkarni", "2025-12-15 10:00:00", "APPROVED", "2025-12-16 11:30:00",
                "2025-12-10 14:00:00"
            ))
            int_id = f"INT-2026-{idx+1:03d}"
            internships.append((
                int_id, sub_id, usn, placed_comp, "Software Engineering Intern", "Enterprise Software",
                "PLACED_COMPANY", f"Senior Mentor ({placed_comp})", "Dr. Ramesh Kulkarni",
                "2026-01-05", "2026-05-05", "4 Months", "ONGOING", "2026-01-05 09:00:00"
            ))
            # Add Progress Report
            progress_reports.append((
                f"REP-{idx+1:03d}-1", int_id, usn, "Weeks 1-4", "2026-02-05 17:00:00",
                "Completed enterprise architecture onboarding, configured Dockerized microservice environment, and deployed initial service-mesh test harness.",
                "Docker, Spring Cloud, AWS IAM, Git Workflows",
                "Complex service-mesh security policies during local integration testing.",
                "Implement OAuth2 JWT authentication filter for the payment gateway microservice.",
                160, "Consistent progress. High code quality and adherence to enterprise CI/CD standards.", "REVIEWED"
            ))
            # Add Evaluation
            m_sc = round(36.0 + (idx % 4) * 0.8, 1)
            p_sc = round(27.0 + (idx % 3) * 0.7, 1)
            r_sc = round(25.0 + (idx % 3) * 0.6, 1)
            tot_sc = round(m_sc + p_sc + r_sc, 1)
            grd = "S" if tot_sc >= 90 else "A"
            st = "PENDING_APPROVAL" if idx < 14 else "FINALIZED"
            evaluations.append((
                f"EVAL-2026-{idx+1:03d}", int_id, usn,
                "Demonstrates exceptional proficiency in enterprise cloud architecture and distributed microservices.",
                "Completed all core deliverables ahead of sprint deadlines with thorough unit test coverage.",
                m_sc, p_sc, r_sc, tot_sc, grd, 12,
                "Dr. Ramesh Kulkarni", st, "2026-03-01 11:00:00"
            ))
    
        # 2. Benchmark specific student Rahul Kumar (1KG21CS045) -> PENDING REVIEW
        elif usn == "1KG21CS045":
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                "Tata Consultancy Services (TCS)", "Research & Innovation Intern",
                "ABC Technologies", "AI/ML Intern",
                "SUBMITTED", "PENDING", None,
                None, None, None,
                None, None, "PENDING", None,
                now_str
            ))
    
        # 3. Benchmark specific student Rohan Verma (1KG21CS072) -> CORRECTION_REQUIRED
        elif usn == "1KG21CS072":
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                "PQR Solutions", "Full Stack Web Developer Intern",
                "XYZ Labs", "Data Science Intern",
                "CORRECTION_REQUIRED", "NEEDS_REVISION", "Please attach the signed college NOC and company stipend guarantee letter.",
                None, None, None,
                "Dr. Ramesh Kulkarni", now_str, "PENDING", None,
                "2026-01-15 11:20:00"
            ))
    
        # 4. Benchmark specific student Sneha Patil (1KG21CS099) -> REJECTED (Backlogs)
        elif usn == "1KG21CS099" or backlogs > 0:
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                "GlobalTech Systems", "Cloud DevOps Intern",
                "Wipro Limited", "Systems Intern",
                "REJECTED", "REJECTED", "Ineligible due to active backlog. Academic regulations require clearing all backlogs prior to Semester 8 internship.",
                None, None, None,
                "Dr. Ramesh Kulkarni", "2026-01-18 16:45:00", "REJECTED", "2026-01-19 10:00:00",
                "2026-01-16 09:30:00"
            ))
    
        # 5. Remaining Normal Students:
        # 26 Approved, 10 Submitted/Pending, 2 Corrections, 2 Rejected
        elif idx < 47:  # Approved Internships
            comp_info = approved_companies_pool[idx % len(approved_companies_pool)]
            c_name, c_role, c_loc, c_mentor = comp_info
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                c_name, c_role,
                "Infosys Limited", "Software Intern",
                "COORDINATOR_APPROVED", "APPROVED", f"Eligibility verified (CGPA {cgpa} >= cutoff). Offer letter validated.",
                c_name, c_role, "4 Months",
                "Dr. Ramesh Kulkarni", "2026-01-20 14:00:00", "APPROVED", "2026-01-21 11:00:00",
                "2026-01-12 10:15:00"
            ))
            int_id = f"INT-2026-{idx+1:03d}"
            internships.append((
                int_id, sub_id, usn, c_name, c_role, "Software Engineering",
                "NORMAL", c_mentor, "Dr. Ramesh Kulkarni",
                "2026-01-15", "2026-05-15", "4 Months", "ONGOING", "2026-01-15 09:00:00"
            ))
            # Add Progress Report
            progress_reports.append((
                f"REP-{idx+1:03d}-1", int_id, usn, "Weeks 1-4", "2026-02-15 18:00:00",
                f"Implemented core domain sprint tasks at {c_name}. Developed REST endpoints and resolved integration issues.",
                "Python, Docker, SQL, Git",
                "Handling latency in high-throughput database connection pools.",
                "Complete sprint milestone and submit mid-term evaluation artifacts.",
                160, "Good performance. Diligent and proactive in team scrums.", "REVIEWED"
            ))
            # Add Evaluation
            m_sc = round(31.0 + (idx % 6) * 1.0, 1)
            p_sc = round(24.0 + (idx % 4) * 0.8, 1)
            r_sc = round(22.0 + (idx % 4) * 0.7, 1)
            tot_sc = round(m_sc + p_sc + r_sc, 1)
            grd = "S" if tot_sc >= 90 else ("A" if tot_sc >= 80 else "B")
            st = "PENDING_APPROVAL" if idx < 14 else "FINALIZED"
            evaluations.append((
                f"EVAL-2026-{idx+1:03d}", int_id, usn,
                f"Strong analytical mindset and practical software development skills demonstrated at {c_name}.",
                "Punctual in weekly scrum meetings and thorough in code documentation.",
                m_sc, p_sc, r_sc, tot_sc, grd, 12,
                "Dr. Ramesh Kulkarni", st, "2026-03-01 15:30:00"
            ))
    
        elif idx < 58: # 10 Pending Reviews
            c_info = approved_companies_pool[(idx * 3) % len(approved_companies_pool)]
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                c_info[0], c_info[1],
                "ABC Technologies", "AI/ML Intern",
                "SUBMITTED", "PENDING", None,
                None, None, None,
                None, None, "PENDING", None,
                (now - timedelta(days=idx-47)).strftime("%Y-%m-%d %H:%M:%S")
            ))
    
        elif idx < 61: # Corrections
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                "DEF AI", "Research Intern",
                "XYZ Labs", "Data Science Intern",
                "CORRECTION_REQUIRED", "NEEDS_REVISION", "Internship duration stated as 8 weeks. Must be amended to minimum 12-16 weeks as per academic regulations.",
                None, None, None,
                "Dr. Ramesh Kulkarni", now_str, "PENDING", None,
                "2026-01-22 15:10:00"
            ))
        else: # Rejected
            submissions.append((
                sub_id, usn, 1, "NORMAL",
                None, None, None,
                "Quantum Apex AI", "Web3 Intern",
                "CyberPhantom Blockchain", "Smart Contract Intern",
                "REJECTED", "REJECTED", "Company not registered with MCA and has no valid university MoU. Disallowed under Faculty Rubric SEC-2.1.",
                None, None, None,
                "Dr. Ramesh Kulkarni", now_str, "REJECTED", now_str,
                "2026-01-20 16:00:00"
            ))
    
    # Insert Submissions
    cursor.executemany("""
    INSERT INTO student_submissions (
        id, student_usn, submission_version, submission_type,
        placed_company_name, placement_details, placed_duration,
        pref_1_company, pref_1_role, pref_2_company, pref_2_role,
        status, coordinator_decision, coordinator_comments,
        approved_company, approved_role, approved_duration,
        coordinator_id, coordinator_timestamp, hod_status, hod_timestamp, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, submissions)
    
    # Insert Internships
    cursor.executemany("""
    INSERT INTO internships (
        id, submission_id, student_usn, company, role, domain, internship_type,
        mentor_name, coordinator_name, start_date, expected_end_date, duration, status, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, internships)
    
    # Insert Progress Reports
    cursor.executemany("""
    INSERT INTO progress_reports (
        id, internship_id, student_usn, reporting_period, submission_date,
        work_completed, skills_learned, challenges, next_objectives, hours_logged, mentor_comments, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, progress_reports)
    
    # Insert Evaluations
    cursor.executemany("""
    INSERT INTO evaluations (
        id, internship_id, student_usn, employer_feedback, mentor_assessment,
        mentor_score, presentation_score, report_score, total_score, proposed_grade,
        academic_credits, evaluator_name, approval_status, evaluated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, evaluations)
    
    # Update Vacancies in opportunities table to match the approved internships
    cursor.execute("UPDATE opportunities SET filled_vacancies = 0, available_vacancies = total_vacancies;")
    counts = cursor.execute("SELECT approved_company, count(*) FROM student_submissions WHERE status IN ('CONFIRMED', 'COORDINATOR_APPROVED') AND approved_company IS NOT NULL GROUP BY approved_company").fetchall()
    for comp, cnt in counts:
        cursor.execute("""
        UPDATE opportunities 
        SET filled_vacancies = MIN(total_vacancies, ?), 
            available_vacancies = MAX(0, total_vacancies - ?)
        WHERE company = ?
        """, (cnt, cnt, comp))
    
    conn.commit()
    conn.close()
    print("SUCCESS: Real-world college data seeded cleanly with 65 authentic students!")

if __name__ == '__main__':
    seed()