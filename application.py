from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import logging
from logging.handlers import RotatingFileHandler
from google_auth_oauthlib.flow import Flow
from google_calendar import (
    get_calendar_service,
    get_user_credentials,
    save_user_credentials,
    get_authorization_url,
    CLIENT_SECRETS_FILE,
    SCOPES,
    delete_user_credentials,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
from google.auth.transport.requests import Request
from ai_features import (
    Profile,
    generate_resume_sections,
    generate_resume_html,
    recommend_jobs_for_user,
    score_answer_against_keywords,
    build_career_plan,
)

app = Flask(__name__)
app.debug = True

# Basic logging configuration
if not app.logger.handlers:
    os.makedirs('logs', exist_ok=True)
    handler = RotatingFileHandler('logs/app.log', maxBytes=1024 * 1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)

# PostgreSQL database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///jobs.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-very-secure-secret-key-12345'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}

# Session security hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True if os.getenv('FLASK_ENV') == 'production' else False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

db = SQLAlchemy(app)


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_employer = db.Column(db.Boolean, default=False)
    company = db.Column(db.String(100))
    title = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    skills = db.Column(db.String(500))
    resume_path = db.Column(db.String(200))
    profile_image = db.Column(db.String(200))  # Added for profile image
    jobs = db.relationship('Job', backref='employer', lazy=True)
    applications = db.relationship('Application', backref='applicant', lazy=True)
    activities = db.relationship('Activity', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.String(500), nullable=False)
    location = db.Column(db.String(100))
    salary = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applications = db.relationship('Application', backref='job', lazy=True)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    resume_path = db.Column(db.String(200))
    cover_letter = db.Column(db.Text)
    date_applied = db.Column(db.DateTime, default=datetime.utcnow)
    interview_date = db.Column(db.DateTime)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    message = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


class InterviewSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    is_booked = db.Column(db.Boolean, default=False)


class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('interview_slot.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    status = db.Column(db.String(20), default='Scheduled')
    notes = db.Column(db.Text)
    meeting_link = db.Column(db.String(200))
    application = db.relationship('Application', backref='interviews')
    slot = db.relationship('InterviewSlot', backref='interviews')


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class UserSkill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='user_skills')
    skill = db.relationship('Skill', backref='user_skills')


class PortfolioLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(200))
    user = db.relationship('User', backref='portfolio_links')


class LearningResource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    resource_type = db.Column(db.String(50))  # e.g., 'Course', 'Certification', 'Article'
    skill = db.relationship('Skill', backref='learning_resources')


# Helper Functions
def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def create_activity(user_id, message, job_id=None):
    activity = Activity(
        user_id=user_id,
        job_id=job_id,
        message=message
    )
    db.session.add(activity)
    db.session.commit()


def calculate_match_percentage(user_skills, job_skills):
    user_skill_set = {skill.skill.name.lower() for skill in user_skills}
    job_skill_list = [skill.strip().lower() for skill in job_skills.split(',')]

    if not job_skill_list:
        return 0, [], []

    matching_skills = user_skill_set.intersection(job_skill_list)
    missing_skills = set(job_skill_list) - user_skill_set
    match_percentage = (len(matching_skills) / len(job_skill_list)) * 100 if job_skill_list else 0

    return match_percentage, list(matching_skills), list(missing_skills)


# Routes
@app.route('/')
def home():
    return render_template('landing.html')


# ---------- AI Features ----------
@app.route('/ai/resume-builder', methods=['GET', 'POST'])
def ai_resume_builder():
    if 'user_id' not in session:
        flash('Please login to use the AI Resume Builder', 'info')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        variant = request.form.get('template', 'classic')
        skills_list = [s.strip() for s in (user.skills or '').split(',') if s.strip()]
        profile = Profile(
            name=user.name,
            title=user.title or ('Employer' if user.is_employer else 'Job Seeker'),
            email=user.email,
            phone=user.phone or '',
            location=user.location or '',
            skills=skills_list,
        )
        sections = generate_resume_sections(profile)
        resume_html = generate_resume_html(sections, template_variant=variant)
        return render_template('resume_result.html', resume_html=resume_html, template_variant=variant)
    return render_template('resume_builder.html', user=user)


@app.route('/ai/job-matching', methods=['GET', 'POST'])
def ai_job_matching():
    if 'user_id' not in session:
        flash('Please login to get personalized job matching', 'info')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    prefs = {}
    if request.method == 'POST':
        prefs['location'] = request.form.get('preferred_location', '')
    jobs = Job.query.order_by(Job.date_posted.desc()).all()
    recommendations = recommend_jobs_for_user(user, jobs, preferences=prefs)
    return render_template('job_matching.html', recommendations=recommendations, prefs=prefs)


@app.route('/ai/interview-prep')
def ai_interview_prep():
    if 'user_id' not in session:
        flash('Please login to access interview preparation', 'info')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    # Use user skills as keywords
    keywords = [s.strip() for s in (user.skills or '').split(',') if s.strip()]
    return render_template('interview_prep.html', keywords=keywords)


@app.route('/ai/interview-feedback', methods=['POST'])
def ai_interview_feedback():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    user = User.query.get(session['user_id'])
    keywords = [s.strip() for s in (user.skills or '').split(',') if s.strip()]
    answer = request.form.get('answer', '')
    feedback = score_answer_against_keywords(answer, keywords)
    return jsonify(feedback)


@app.route('/ai/career-path')
def ai_career_path():
    if 'user_id' not in session:
        flash('Please login to see your career path', 'info')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    skills_list = [s.strip() for s in (user.skills or '').split(',') if s.strip()]
    plan = build_career_plan(skills_list)
    return render_template('career_path.html', plan=plan)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        app.logger.info('Login attempt initiated')
        email = request.form.get('email')
        password = request.form.get('password')
        is_employer = 'role' in request.form and request.form.get('role') == 'employer'

        if not email or not password:
            app.logger.warning('Login failed: missing email or password')
            flash('Email and password are required', 'danger')
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            app.logger.warning('Login failed: invalid credentials for %s', email)
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

        if user.is_employer != is_employer:
            app.logger.warning('Login failed: role mismatch for user_id=%s', user.id)
            flash('Please select the correct account type', 'danger')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['is_employer'] = user.is_employer
        session.permanent = True
        app.logger.info('Login successful: user_id=%s is_employer=%s', user.id, user.is_employer)
        flash('Login successful!', 'success')

        return redirect(url_for('employer_dashboard' if user.is_employer else 'dashboard'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            is_employer = 'is_employer' in request.form and request.form.get('is_employer') == 'on'
            company = request.form.get('company_name') if is_employer else None

            if not all([name, email, password]):
                app.logger.warning('Registration failed: missing required fields')
                flash('All fields are required', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(email=email).first():
                app.logger.warning('Registration failed: email already registered %s', email)
                flash('Email already registered', 'danger')
                return redirect(url_for('register'))

            user = User(
                name=name,
                email=email,
                is_employer=is_employer,
                company=company
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            session['user_id'] = user.id
            session['is_employer'] = is_employer
            session.permanent = True
            app.logger.info('Registration successful: user_id=%s is_employer=%s', user.id, is_employer)
            flash('Registration successful!', 'success')

            return redirect(url_for('employer_dashboard' if is_employer else 'dashboard'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Registration error: %s', str(e))
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    # Best-effort token cleanup for Google OAuth credentials
    if user_id:
        try:
            delete_user_credentials(user_id)
        except Exception:
            app.logger.warning('Failed token revocation for user_id=%s', user_id)
    session.clear()
    app.logger.info('Logout successful: user_id=%s', user_id)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


# Employer Routes
@app.route('/employer/dashboard')
def employer_dashboard():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    employer = User.query.get(session['user_id'])
    jobs = Job.query.filter_by(employer_id=employer.id).all()

    # Get total applications across all jobs
    total_applications = 0
    for job in jobs:
        total_applications += len(job.applications)

    # Get number of scheduled interviews
    interviews_scheduled = Application.query.filter(
        Application.job.has(employer_id=employer.id),
        Application.status == 'Interview Scheduled'
    ).count()
    
    # Get scheduled interview details for employer's jobs
    scheduled_interviews = db.session.query(Interview, Application, Job, User).\
        join(Application, Interview.application_id == Application.id).\
        join(Job, Application.job_id == Job.id).\
        join(User, Application.user_id == User.id).\
        filter(Job.employer_id == employer.id).all()
    
    # Get counts for analytics section
    pending_count = Application.query.join(Job).filter(
        Job.employer_id == employer.id,
        Application.status == 'Pending'
    ).count()
    
    reviewing_count = Application.query.join(Job).filter(
        Job.employer_id == employer.id,
        Application.status == 'Reviewing'
    ).count()

    # Get recent activities
    activities = Activity.query.filter_by(user_id=employer.id).order_by(Activity.date.desc()).limit(4).all()
    
    today = datetime.utcnow()

    return render_template('employer_dashboard.html',
                           employer=employer,
                           jobs=jobs,
                           total_applications=total_applications,
                           interviews=interviews_scheduled,
                           scheduled_interviews=scheduled_interviews,
                           activities=activities,
                           today=today,
                           pending_count=pending_count,
                           reviewing_count=reviewing_count)


@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        employer = User.query.get(session['user_id'])
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        required_skills = (request.form.get('required_skills') or '').strip()
        location = (request.form.get('location') or '').strip()
        salary_range = (request.form.get('salary_range') or '').strip()

        if not title or not description or not required_skills:
            flash('Title, description, and required skills are required.', 'danger')
            return render_template('post_job.html')

        try:
            job = Job(
                title=title,
                company=employer.company or "Company Name",
                description=description,
                required_skills=required_skills,
                location=location,
                salary=salary_range,
                employer_id=employer.id
            )

            db.session.add(job)
            db.session.flush()  # get job.id early for activity association if needed
            create_activity(employer.id, f"Posted new job: {job.title}", job_id=job.id)
            db.session.commit()
            flash('Job posted successfully!', 'success')
            return redirect(url_for('employer_dashboard'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Post job error: %s', str(e))
            flash(f'Could not post job: {e}', 'danger')
            return render_template('post_job.html')

    # GET request: render the job posting form
    return render_template('post_job.html')

@app.route('/authorize')
def authorize():
    try:
        redirect_uri = url_for('oauth2callback', _external=True)
        auth_url, state = get_authorization_url(redirect_uri)
        session['state'] = state
        return redirect(auth_url)
    except FileNotFoundError:
        app.logger.error('Missing client_secret.json for Google OAuth')
        flash('Google OAuth configuration file is missing. Please add client_secret.json.', 'danger')
        return redirect(url_for('employer_dashboard'))
    except Exception as e:
        app.logger.exception('Authorize error: %s', str(e))
        flash(f'Error initializing Google OAuth: {e}', 'danger')
        return redirect(url_for('employer_dashboard'))

@app.route('/oauth2callback')
def oauth2callback():
    state = session.pop('state', None)
    if not state or state != request.args.get('state'):
        flash('Invalid state parameter.', 'danger')
        return redirect(url_for('employer_dashboard'))

    redirect_uri = url_for('oauth2callback', _external=True)
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=redirect_uri)
    
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    
    user_id = session.get('user_id')
    if user_id:
        save_user_credentials(user_id, credentials)
        flash('Google Calendar authorized successfully!', 'success')
    else:
        flash('User not found in session.', 'danger')

    return redirect(url_for('employer_dashboard'))


@app.route('/schedule_interview_form/<int:application_id>', methods=['GET', 'POST'])
def schedule_interview_form(application_id):
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please log in as an employer to access this page.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    credentials = get_user_credentials(user_id)
    # Attempt to refresh expired credentials if refresh token is available
    if not credentials:
        return redirect(url_for('authorize'))
    if getattr(credentials, 'expired', False):
        try:
            if getattr(credentials, 'refresh_token', None):
                credentials.refresh(Request())
                save_user_credentials(user_id, credentials)
            else:
                return redirect(url_for('authorize'))
        except Exception as e:
            app.logger.exception('Credential refresh error: %s', str(e))
            return redirect(url_for('authorize'))

    application = Application.query.get_or_404(application_id)
    if request.method == 'POST':
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        summary = request.form['summary']
        description = request.form['description']

        service = get_calendar_service(credentials)

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
            'attendees': [
                {'email': application.applicant.email},
                {'email': application.job.employer.email}
            ],
        }

        try:
            service.events().insert(calendarId='primary', body=event).execute()
            flash('Interview scheduled successfully!', 'success')
            application.status = 'Interview Scheduled'
            db.session.commit()
            return redirect(url_for('view_applications', job_id=application.job_id))
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    return render_template('schedule_interview.html', application=application)


@app.route('/view_applications/<int:job_id>')
def view_applications(job_id):
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    job = Job.query.get_or_404(job_id)

    # Ensure the employer owns this job
    if job.employer_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('employer_dashboard'))

    applications = Application.query.filter_by(job_id=job.id).all()
    return render_template('view_applications.html', job=job, applications=applications)


@app.route('/analytics')
def analytics():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    employer = User.query.get(session['user_id'])
    jobs = Job.query.filter_by(employer_id=employer.id).all()

    # Get total applications across all jobs
    total_applications = 0
    for job in jobs:
        total_applications += len(job.applications)

    return render_template('analytics.html',
                           employer=employer,
                           jobs=jobs,
                           total_applications=total_applications)


@app.route('/admin/seed-curated-jobs')
def admin_seed_curated_jobs():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))
    try:
        from database_updates import add_curated_job_postings
        add_curated_job_postings()
        flash('Curated job postings added (if needed).', 'success')
    except Exception as e:
        app.logger.exception('Seeding error: %s', str(e))
        flash(f'Error seeding jobs: {e}', 'danger')
    return redirect(url_for('employer_dashboard'))


@app.route('/all_applications')
def all_applications():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    employer_id = session['user_id']
    applications = Application.query.join(Job).filter(Job.employer_id == employer_id).order_by(Application.date_applied.desc()).all()
    
    return render_template('all_applications.html', applications=applications)


@app.route('/update_application_status/<int:application_id>', methods=['POST'])
def update_application_status(application_id):
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))
    
    application = Application.query.get_or_404(application_id)
    job = Job.query.get(application.job_id)
    
    # Ensure the employer owns this job
    if job.employer_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('employer_dashboard'))
    
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Reviewing', 'Accepted', 'Rejected']:
        application.status = new_status
        db.session.commit()
        flash('Application status updated successfully', 'success')
    
    return redirect(url_for('all_applications'))


@app.route('/all_activities')
def all_activities():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    activities = Activity.query.filter_by(user_id=user_id).order_by(Activity.date.desc()).all()
    
    today = datetime.utcnow()
    
    return render_template('all_activities.html', activities=activities, today=today)


# Job Seeker Routes
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login', 'danger')
        return redirect(url_for('login'))

    if session.get('is_employer'):
        return redirect(url_for('employer_dashboard'))

    user = User.query.get(session['user_id'])
    applications = Application.query.filter_by(user_id=user.id).all()

    stats = {
        'total': len(applications),
        'reviewing': len([a for a in applications if a.status == 'Reviewing']),
        'accepted': len([a for a in applications if a.status == 'Accepted']),
        'rejected': len([a for a in applications if a.status == 'Rejected']),
        'interviews_scheduled': len([a for a in applications if a.status == 'Interview Scheduled']),
        'saved_jobs': 0  # Placeholder for future feature
    }

    recent_activities = Activity.query.filter_by(user_id=user.id).order_by(Activity.date.desc()).limit(4).all()
    
    today = datetime.utcnow()

    return render_template('employee_dashboard.html',
                           user=user,
                           applications=applications,
                           stats=stats,
                           recent_activities=recent_activities,
                           today=today)


@app.route('/jobs')
def jobs():
    query = request.args.get('q', '')

    if query:
        # Simple search implementation
        search = f"%{query}%"
        jobs = Job.query.filter(
            (Job.title.ilike(search)) |
            (Job.company.ilike(search)) |
            (Job.required_skills.ilike(search))
        ).order_by(Job.date_posted.desc()).all()
    else:
        jobs = Job.query.order_by(Job.date_posted.desc()).all()

    return render_template('jobs.html', jobs=jobs)


@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Calculate match percentage if user is logged in
    match_percentage = 0
    if 'user_id' in session and not session.get('is_employer'):
        user = User.query.get(session['user_id'])
        match_percentage = calculate_match_percentage(user.skills, job.required_skills)
    
    return render_template('job_detail.html', job=job, match_percentage=match_percentage)


@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    if 'user_id' not in session:
        flash('Please login to apply for jobs', 'info')
        return redirect(url_for('login'))
    
    if session.get('is_employer'):
        flash('Employer accounts cannot apply for jobs', 'warning')
        return redirect(url_for('jobs'))
    
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            
            # Check if already applied
            existing_application = Application.query.filter_by(user_id=user_id, job_id=job_id).first()
            if existing_application:
                flash('You have already applied for this job', 'info')
                return redirect(url_for('jobs'))
            
            # Resume upload
            resume_path = None
            if 'resume' in request.files:
                resume_file = request.files['resume']
                if resume_file and allowed_file(resume_file.filename):
                    filename = secure_filename(f"{user_id}_{job_id}_{resume_file.filename}")
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    resume_path = os.path.join('uploads', filename)
                    resume_file.save(os.path.join('static', resume_path))
            
            # Create application
            application = Application(
                user_id=user_id,
                job_id=job_id,
                status='Pending',
                resume_path=resume_path,
                cover_letter=request.form.get('coverLetter', '')
            )
            
            db.session.add(application)
            
            # Create activity for both user and employer
            create_activity(user_id, f"Applied for {job.title} at {job.company}")
            create_activity(job.employer_id, f"New application for {job.title}", job_id)
            
            db.session.commit()
            flash('Your application was submitted successfully!', 'success')
            return redirect(url_for('dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('apply', job_id=job_id))
    
    return render_template('apply.html', job=job)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        # Update basic info
        user.name = request.form.get('name')
        user.title = request.form.get('title')
        user.phone = request.form.get('phone')
        user.location = request.form.get('location')

        # Handle profile image upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"profile_{user.id}_{filename}")
                file.save(filepath)
                user.profile_image = f"profile_{user.id}_{filename}"

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    all_skills = Skill.query.all()
    return render_template('profile.html', user=user, all_skills=all_skills)


@app.route('/manage_slots', methods=['GET', 'POST'])
def manage_slots():
    if 'user_id' not in session or not session.get('is_employer'):
        flash('Please login as employer', 'danger')
        return redirect(url_for('login'))
    
    employer_id = session['user_id']
    
    if request.method == 'POST':
        start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        
        if start_time >= end_time:
            flash('End time must be after start time', 'danger')
            return redirect(url_for('manage_slots'))
        
        slot = InterviewSlot(
            employer_id=employer_id,
            start_time=start_time,
            end_time=end_time
        )
        
        db.session.add(slot)
        db.session.commit()
        flash('Interview slot added successfully', 'success')
        return redirect(url_for('manage_slots'))
    
    slots = InterviewSlot.query.filter_by(employer_id=employer_id).all()
    return render_template('interview_slots.html', slots=slots)


@app.route('/schedule_interview/<int:application_id>', methods=['GET', 'POST'])
def schedule_interview_route(application_id):
    if 'user_id' not in session:
        flash('Please login', 'danger')
        return redirect(url_for('login'))
    
    application = Application.query.get_or_404(application_id)
    
    # Check if user is the employer who posted the job
    if session.get('is_employer'):
        job = Job.query.get(application.job_id)
        if job.employer_id != session.get('user_id'):
            flash('Unauthorized access', 'danger')
            return redirect(url_for('employer_dashboard'))
    # Check if user is the applicant
    elif application.user_id != session['user_id']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        slot_id = request.form.get('slot_id')
        slot = InterviewSlot.query.get(slot_id)
        
        if slot.is_booked:
            flash('This slot is already booked', 'danger')
            return redirect(url_for('schedule_interview', application_id=application_id))
        
        interview = Interview(
            slot_id=slot_id,
            application_id=application_id,
            meeting_link=f"https://meet.luminate.com/{slot_id}",  # Placeholder
            notes=""
        )
        
        slot.is_booked = True
        application.status = 'Interview Scheduled'
        
        db.session.add(interview)
        
        # Create activities
        create_activity(application.user_id, f"Interview scheduled for {application.job.title}")
        create_activity(application.job.employer_id, f"Interview scheduled with {application.applicant.name}", application.job_id)
        
        db.session.commit()
        flash('Interview scheduled successfully', 'success')
        
        if session.get('is_employer'):
            return redirect(url_for('view_applications', job_id=application.job_id))
        else:
            return redirect(url_for('interviews'))
    
    # Get available slots
    if session.get('is_employer'):
        slots = InterviewSlot.query.filter_by(employer_id=session['user_id'], is_booked=False).all()
    else:
        job = Job.query.get(application.job_id)
        slots = InterviewSlot.query.filter_by(employer_id=job.employer_id, is_booked=False).all()
    
    # Get existing interview if any
    interview = Interview.query.filter_by(application_id=application_id).first()
    
    return render_template('schedule_interview.html', application=application, slots=slots, interview=interview)


@app.route('/interviews')
def interviews():
    if 'user_id' not in session:
        flash('Please login', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    from sqlalchemy.orm import joinedload
    if session.get('is_employer'):
        # For employers - interviews for their jobs
        interviews = Interview.query.join(Application).join(Job)\
            .options(joinedload(Interview.slot), joinedload(Interview.application).joinedload(Application.job))\
            .filter(Job.employer_id == user_id).all()
    else:
        # For job seekers - interviews for their applications
        interviews = Interview.query.join(Application)\
            .options(joinedload(Interview.slot), joinedload(Interview.application).joinedload(Application.job))\
            .filter(Application.user_id == user_id).all()
    
    return render_template('interviews.html', interviews=interviews, user=User.query.get(user_id))


@app.route('/results')
def results():
    if 'user_id' not in session or session.get('is_employer'):
        flash('Please login as job seeker', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if user.user_skills:
        all_jobs = Job.query.all()
        recommended_jobs = []

        for job in all_jobs:
            match_percentage, matching_skills, missing_skills = calculate_match_percentage(user.user_skills, job.required_skills)
            if match_percentage > 0:
                learning_recommendations = {}
                if missing_skills:
                    for skill_name in missing_skills:
                        skill = Skill.query.filter(Skill.name.ilike(skill_name)).first()
                        if skill:
                            resources = LearningResource.query.filter_by(skill_id=skill.id).limit(3).all()
                            if resources:
                                learning_recommendations[skill_name] = resources

                recommended_jobs.append({
                    'job': job,
                    'match_percentage': round(match_percentage),
                    'matching_skills': matching_skills,
                    'missing_skills': missing_skills,
                    'learning_recommendations': learning_recommendations
                })
        
        # Sort by match percentage (highest first)
        recommended_jobs.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        return render_template('results.html', matches=recommended_jobs)
    else:
        flash('Please add skills to your profile to get job recommendations', 'info')
        return redirect(url_for('profile'))


@app.route('/skills', methods=['GET', 'POST'])
def skills():
    if request.method == 'POST':
        skill_name = request.form.get('skill_name')
        if skill_name and not Skill.query.filter_by(name=skill_name).first():
            new_skill = Skill(name=skill_name)
            db.session.add(new_skill)
            db.session.commit()
            flash('Skill added successfully!', 'success')
        else:
            flash('Skill already exists or is invalid.', 'danger')
    all_skills = Skill.query.all()
    return render_template('skills.html', skills=all_skills)


@app.route('/add-skill', methods=['POST'])
def add_skill():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    skill_name = request.form.get('skill_name')
    if skill_name:
        skill = Skill.query.filter_by(name=skill_name).first()
        if not skill:
            skill = Skill(name=skill_name)
            db.session.add(skill)
            db.session.commit()

        user_skill = UserSkill.query.filter_by(user_id=user_id, skill_id=skill.id).first()
        if not user_skill:
            new_user_skill = UserSkill(user_id=user_id, skill_id=skill.id)
            db.session.add(new_user_skill)
            db.session.commit()
            flash('Skill added to your profile.', 'success')
        else:
            flash('Skill already in your profile.', 'info')
    return redirect(url_for('profile'))


@app.route('/add-portfolio-link', methods=['POST'])
def add_portfolio_link():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    url = request.form.get('url')
    description = request.form.get('description')

    if url:
        new_link = PortfolioLink(user_id=user_id, url=url, description=description)
        db.session.add(new_link)
        db.session.commit()
        flash('Portfolio link added.', 'success')
    else:
        flash('URL is required.', 'danger')

    return redirect(url_for('profile'))


@app.route('/learning-resources', methods=['GET', 'POST'])
def learning_resources():
    if request.method == 'POST':
        title = request.form.get('title')
        url = request.form.get('url')
        resource_type = request.form.get('resource_type')
        skill_id = request.form.get('skill_id')

        if all([title, url, resource_type, skill_id]):
            new_resource = LearningResource(
                title=title,
                url=url,
                resource_type=resource_type,
                skill_id=skill_id
            )
            db.session.add(new_resource)
            db.session.commit()
            flash('Learning resource added.', 'success')
        else:
            flash('All fields are required.', 'danger')

    all_skills = Skill.query.all()
    all_resources = LearningResource.query.all()
    return render_template('learning_resources.html', skills=all_skills, resources=all_resources)


@app.before_first_request
def auto_seed_curated_jobs():
    try:
        job_count = Job.query.count()
        if job_count < 15:
            from database_updates import add_curated_job_postings
            add_curated_job_postings()
            app.logger.info('Auto-seeded curated job postings.')
    except Exception as e:
        app.logger.warning(f'Auto-seeding skipped due to error: {e}')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.getenv('PORT', '5001'))
    app.run(debug=True, port=port)
