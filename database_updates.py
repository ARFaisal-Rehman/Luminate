from application import db, User, Job, Application, Activity, InterviewSlot, Interview
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import random
import csv


def add_sample_data():
    """Add sample data to the database for testing purposes"""
    print("Adding sample data to the database...")

    # Clear existing data
    db.session.query(Interview).delete()
    db.session.query(InterviewSlot).delete()
    db.session.query(Activity).delete()
    db.session.query(Application).delete()
    db.session.query(Job).delete()
    db.session.query(User).delete()
    db.session.commit()

    # Create employer accounts
    employer1 = User(
        name="TechCorp Inc.",
        email="employer@techcorp.com",
        is_employer=True,
        company="TechCorp Inc.",
        phone="555-123-4567",
        location="San Francisco, CA"
    )
    employer1.set_password("password123")

    employer2 = User(
        name="Creative Solutions",
        email="employer@creativesolutions.com",
        is_employer=True,
        company="Creative Solutions",
        phone="555-987-6543",
        location="New York, NY"
    )
    employer2.set_password("password123")

    db.session.add_all([employer1, employer2])
    db.session.commit()

    # Create job seeker accounts
    seeker1 = User(
        name="John Smith",
        email="john@example.com",
        is_employer=False,
        title="Senior Software Engineer",
        phone="555-111-2222",
        location="San Francisco, CA",
        skills="Python, JavaScript, React, SQL, AWS"
    )
    seeker1.set_password("password123")

    seeker2 = User(
        name="Sarah Johnson",
        email="sarah@example.com",
        is_employer=False,
        title="UX/UI Designer",
        phone="555-333-4444",
        location="Remote",
        skills="UI Design, Figma, Sketch, User Research, Prototyping"
    )
    seeker2.set_password("password123")

    db.session.add_all([seeker1, seeker2])
    db.session.commit()

    # Create job listings
    job1 = Job(
        title="Senior Full Stack Developer",
        company="TechCorp Inc.",
        description="""
        We're looking for a talented Full Stack Developer to join our team.

        Responsibilities:
        - Design and develop web applications using modern technologies
        - Work with product and design teams to implement new features
        - Optimize applications for performance and scalability
        - Write clean, testable code with appropriate documentation

        Requirements:
        - 5+ years of experience in full stack development
        - Proficiency in Python, JavaScript, and React
        - Experience with SQL databases and AWS
        - Strong problem-solving skills and attention to detail
        """,
        required_skills="Python, JavaScript, React, SQL, AWS",
        location="San Francisco, CA",
        salary="$120,000 - $150,000",
        employer_id=employer1.id
    )

    job2 = Job(
        title="UX/UI Designer",
        company="Creative Solutions",
        description="""
        Join our creative team as a UX/UI Designer and help shape the future of our products.

        Responsibilities:
        - Create user-centered designs for web and mobile applications
        - Conduct user research and usability testing
        - Develop wireframes, prototypes, and visual designs
        - Collaborate with developers to implement designs

        Requirements:
        - 3+ years of experience in UX/UI design
        - Proficiency in design tools such as Figma and Sketch
        - Strong portfolio showcasing your design process
        - Experience with user research and prototyping
        """,
        required_skills="UI Design, Figma, Sketch, User Research, Prototyping",
        location="Remote",
        salary="$90,000 - $110,000",
        employer_id=employer2.id
    )

    job3 = Job(
        title="Data Scientist",
        company="TechCorp Inc.",
        description="""
        We are seeking a skilled Data Scientist to help us extract insights from our data.

        Responsibilities:
        - Analyze large datasets to identify trends and patterns
        - Develop machine learning models and algorithms
        - Create visualizations and reports to communicate findings
        - Collaborate with cross-functional teams to implement data-driven solutions

        Requirements:
        - Master's or PhD in a quantitative field
        - Experience with Python, R, and SQL
        - Knowledge of machine learning and statistical analysis
        - Strong communication and problem-solving skills
        """,
        required_skills="Python, R, SQL, Machine Learning, Statistics",
        location="San Francisco, CA",
        salary="$130,000 - $160,000",
        employer_id=employer1.id
    )

    db.session.add_all([job1, job2, job3])
    db.session.commit()

    # Create applications
    application1 = Application(
        user_id=seeker1.id,
        job_id=job1.id,
        status="Reviewing",
        cover_letter="I am excited to apply for the Senior Full Stack Developer position at TechCorp Inc. With 7 years of experience in full stack development, I believe I would be a great fit for your team.",
        date_applied=datetime.utcnow() - timedelta(days=5)
    )

    application2 = Application(
        user_id=seeker2.id,
        job_id=job2.id,
        status="Interview Scheduled",
        cover_letter="As a UX/UI Designer with 5 years of experience, I am thrilled to apply for the position at Creative Solutions. I am passionate about creating user-centered designs and would love to contribute to your team.",
        date_applied=datetime.utcnow() - timedelta(days=10),
        interview_date=datetime.utcnow() + timedelta(days=2)
    )

    db.session.add_all([application1, application2])
    db.session.commit()

    # Create interview slots
    for i in range(5):
        slot = InterviewSlot(
            employer_id=employer1.id,
            start_time=datetime.utcnow() + timedelta(days=i + 1, hours=10),
            end_time=datetime.utcnow() + timedelta(days=i + 1, hours=11),
            is_booked=False
        )
        db.session.add(slot)

    for i in range(5):
        slot = InterviewSlot(
            employer_id=employer2.id,
            start_time=datetime.utcnow() + timedelta(days=i + 1, hours=14),
            end_time=datetime.utcnow() + timedelta(days=i + 1, hours=15),
            is_booked=(i == 1)  # Make one slot booked
        )
        db.session.add(slot)

    db.session.commit()

    # Create an interview
    booked_slot = InterviewSlot.query.filter_by(employer_id=employer2.id, is_booked=True).first()
    if booked_slot:
        interview = Interview(
            slot_id=booked_slot.id,
            application_id=application2.id,
            status="Scheduled",
            meeting_link="https://zoom.us/j/123456789",
            notes="Candidate has a strong portfolio. Focus on team collaboration experience."
        )
        db.session.add(interview)

    # Create activities
    activities = [
        Activity(user_id=employer1.id, job_id=job1.id, message="Posted new job: Senior Full Stack Developer",
                 date=datetime.utcnow() - timedelta(days=7)),
        Activity(user_id=employer2.id, job_id=job2.id, message="Posted new job: UX/UI Designer",
                 date=datetime.utcnow() - timedelta(days=14)),
        Activity(user_id=employer1.id, job_id=job3.id, message="Posted new job: Data Scientist",
                 date=datetime.utcnow() - timedelta(days=3)),
        Activity(user_id=seeker1.id, job_id=job1.id, message="Applied for Senior Full Stack Developer at TechCorp Inc.",
                 date=datetime.utcnow() - timedelta(days=5)),
        Activity(user_id=seeker2.id, job_id=job2.id, message="Applied for UX/UI Designer at Creative Solutions",
                 date=datetime.utcnow() - timedelta(days=10)),
        Activity(user_id=employer1.id, job_id=job1.id, message="Application from John Smith is now being reviewed",
                 date=datetime.utcnow() - timedelta(days=3)),
        Activity(user_id=employer2.id, job_id=job2.id, message="Scheduled interview with Sarah Johnson",
                 date=datetime.utcnow() - timedelta(days=5)),
        Activity(user_id=seeker2.id, job_id=job2.id, message="Interview scheduled for UX/UI Designer position",
                 date=datetime.utcnow() - timedelta(days=5))
    ]
    db.session.add_all(activities)
    db.session.commit()

    print("Sample data added successfully.")


def import_jobs_from_csv(csv_path, employer_id=None):
    """Import jobs from a CSV file into the Job table. If employer_id is None, assign to a default employer."""
    from application import Job, db, User
    from datetime import datetime
    
    # Find or create a default employer if not provided
    if employer_id is None:
        employer = User.query.filter_by(email="imported_jobs@luminate.com").first()
        if not employer:
            employer = User(
                name="Imported Jobs",
                email="imported_jobs@luminate.com",
                is_employer=True,
                company="Imported Jobs",
                phone="N/A",
                location="N/A"
            )
            employer.set_password("imported123")
            db.session.add(employer)
            db.session.commit()
        employer_id = employer.id

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        for row in reader:
            # Map CSV columns to Job fields
            job = Job(
                title=row.get('Job Title', '').strip(),
                company=row.get('Industry', '').strip() or "Imported Company",
                description=row.get('Role Category', '').strip() or row.get('Functional Area', '').strip() or "No description provided.",
                required_skills=row.get('Key Skills', '').replace('|', ',').strip(),
                location=row.get('Location', '').strip(),
                salary=row.get('Job Salary', '').strip(),
                date_posted=datetime.strptime(row.get('Crawl Timestamp', '').split(' ')[0], '%Y-%m-%d') if row.get('Crawl Timestamp') else datetime.utcnow(),
                employer_id=employer_id
            )
            # Optionally, add a flag for imported jobs if you add such a column
            db.session.add(job)
            count += 1
        db.session.commit()
        print(f"Imported {count} jobs from {csv_path}")


def add_curated_job_postings():
    """Add 15 diverse curated job postings if fewer exist."""
    from application import Job, User, db
    existing = Job.query.count()
    if existing >= 15:
        print(f"Jobs already seeded: {existing}")
        return
    # Ensure a default employer exists
    employer = User.query.filter_by(email='employer@defaultco.com').first()
    if not employer:
        employer = User(
            name='DefaultCo',
            email='employer@defaultco.com',
            is_employer=True,
            company='DefaultCo',
            phone='555-000-0000',
            location='Remote'
        )
        employer.set_password('password123')
        db.session.add(employer)
        db.session.commit()

    postings = [
        # 5 technical roles
        {
            'title': 'Software Engineer', 'company': 'TechCorp',
            'description': 'Build scalable backend services and REST APIs.',
            'required_skills': 'Python, Flask, SQL, Docker, AWS', 'location': 'Remote', 'salary': '$110,000 - $140,000'
        },
        {
            'title': 'Data Scientist', 'company': 'Insight Labs',
            'description': 'Develop ML models and analyze experimental results.',
            'required_skills': 'Python, Pandas, Scikit-learn, SQL, Statistics', 'location': 'San Francisco, CA', 'salary': '$130,000 - $160,000'
        },
        {
            'title': 'Frontend Engineer', 'company': 'PixelWorks',
            'description': 'Build accessible UI and design system components.',
            'required_skills': 'JavaScript, React, CSS, Accessibility, Testing', 'location': 'New York, NY', 'salary': '$100,000 - $130,000'
        },
        {
            'title': 'DevOps Engineer', 'company': 'CloudOps',
            'description': 'Manage CI/CD, infrastructure as code, and monitoring.',
            'required_skills': 'Docker, Kubernetes, Terraform, AWS, Monitoring', 'location': 'Austin, TX', 'salary': '$120,000 - $150,000'
        },
        {
            'title': 'Mobile Developer', 'company': 'Appify',
            'description': 'Develop cross-platform mobile applications.',
            'required_skills': 'Flutter, Dart, REST, CI/CD, UX', 'location': 'Remote', 'salary': '$95,000 - $125,000'
        },
        # 5 non-technical roles
        {
            'title': 'Marketing Specialist', 'company': 'BrightBrand',
            'description': 'Plan and execute digital marketing campaigns.',
            'required_skills': 'SEO, SEM, Analytics, Copywriting, Social Media', 'location': 'Remote', 'salary': '$65,000 - $85,000'
        },
        {
            'title': 'HR Manager', 'company': 'PeopleFirst',
            'description': 'Lead recruitment and employee engagement programs.',
            'required_skills': 'Recruitment, Onboarding, Policy, Communication, Analytics', 'location': 'Chicago, IL', 'salary': '$80,000 - $100,000'
        },
        {
            'title': 'Content Strategist', 'company': 'StoryLine',
            'description': 'Develop content strategies and editorial calendars.',
            'required_skills': 'Content, SEO, Analytics, Communication, Project Management', 'location': 'Remote', 'salary': '$70,000 - $90,000'
        },
        {
            'title': 'Sales Associate', 'company': 'DealMakers',
            'description': 'Drive pipeline growth and client relationships.',
            'required_skills': 'CRM, Communication, Negotiation, Prospecting, Reporting', 'location': 'Dallas, TX', 'salary': '$55,000 - $75,000 + commission'
        },
        {
            'title': 'Customer Support Specialist', 'company': 'HelpHub',
            'description': 'Troubleshoot issues and ensure customer satisfaction.',
            'required_skills': 'Communication, Ticketing, Product Knowledge, Empathy, Writing', 'location': 'Remote', 'salary': '$50,000 - $65,000'
        },
        # 3 managerial positions
        {
            'title': 'Project Manager', 'company': 'PlanIt',
            'description': 'Lead cross-functional teams and deliver projects on time.',
            'required_skills': 'Agile, Communication, Risk Management, Planning, Reporting', 'location': 'Seattle, WA', 'salary': '$100,000 - $130,000'
        },
        {
            'title': 'Department Head', 'company': 'OpsCentral',
            'description': 'Own department strategy and outcomes.',
            'required_skills': 'Leadership, Strategy, Budgeting, Communication, Analytics', 'location': 'Boston, MA', 'salary': '$140,000 - $180,000'
        },
        {
            'title': 'Product Manager', 'company': 'Visionary',
            'description': 'Define product roadmap and deliver customer value.',
            'required_skills': 'Roadmap, UX, Analytics, Communication, Prioritization', 'location': 'Remote', 'salary': '$120,000 - $150,000'
        },
        # 2 administrative roles
        {
            'title': 'Office Administrator', 'company': 'DailyOps',
            'description': 'Manage office operations and scheduling.',
            'required_skills': 'Scheduling, Communication, Tools, Organization, Reporting', 'location': 'Remote', 'salary': '$45,000 - $60,000'
        },
        {
            'title': 'Executive Assistant', 'company': 'C-Suite Partners',
            'description': 'Support executives with logistics and coordination.',
            'required_skills': 'Calendar, Travel, Communication, Confidentiality, Tools', 'location': 'Los Angeles, CA', 'salary': '$60,000 - $80,000'
        },
    ]

    for p in postings:
        job = Job(
            title=p['title'],
            company=p['company'],
            description=p['description'],
            required_skills=p['required_skills'],
            location=p['location'],
            salary=p['salary'],
            employer_id=employer.id,
        )
        db.session.add(job)
    db.session.commit()
    print(f"Seeded {len(postings)} curated jobs.")


if __name__ == "__main__":
    # Create database tables if they don't exist
    db.create_all()

    # Add sample data
    add_sample_data()
