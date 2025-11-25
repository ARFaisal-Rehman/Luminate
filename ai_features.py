from typing import List, Dict, Any, Union
from dataclasses import dataclass
import math


@dataclass
class Profile:
    name: str
    title: str
    email: str
    phone: str
    location: str
    skills: List[str]
    summary: str = ""
    experience: List[Dict[str, Any]] = None
    education: List[Dict[str, Any]] = None
    projects: List[Dict[str, Any]] = None


def normalize_skills(skills_text: str) -> List[str]:
    if not skills_text:
        return []
    return [s.strip().lower() for s in skills_text.split(',') if s.strip()]


def generate_resume_sections(profile: Profile) -> Dict[str, Any]:
    skills = profile.skills or []
    summary = profile.summary or (
        f"{profile.name} is a {profile.title} based in {profile.location} with strengths in "
        + ", ".join(skills[:5])
    )
    return {
        'header': {
            'name': profile.name,
            'title': profile.title,
            'contact': {
                'email': profile.email,
                'phone': profile.phone,
                'location': profile.location,
            },
        },
        'summary': summary,
        'skills': skills,
        'experience': profile.experience or [],
        'education': profile.education or [],
    }


def generate_resume_html(sections_or_profile: Union[Dict[str, Any], Profile], template: str = 'classic') -> str:
    # Simple HTML snippet; final PDF via browser print or html2pdf client-side
    # Support both passing a Profile and precomputed sections
    sections = sections_or_profile if isinstance(sections_or_profile, dict) else generate_resume_sections(sections_or_profile)
    classes = 'resume resume-' + template
    header = sections['header']
    html = f"""
    <div class='{classes}'>
      <section class='resume-header'>
        <h1>{header['name']}</h1>
        <p class='subtitle'>{header['title']}</p>
        <p class='contact'>
          <span>{header['contact']['email']}</span> ·
          <span>{header['contact']['phone']}</span> ·
          <span>{header['contact']['location']}</span>
        </p>
      </section>
      <section class='resume-summary'>
        <h2>Professional Summary</h2>
        <p>{sections['summary']}</p>
      </section>
      <section class='resume-skills'>
        <h2>Skills</h2>
        <ul>"""
    for s in sections['skills']:
        html += f"<li>{s}</li>"
    html += """</ul>
      </section>
    """
    if sections['experience']:
        html += "<section class='resume-experience'><h2>Experience</h2>"
        for exp in sections['experience']:
            period = exp.get('dates') or exp.get('period', '')
            details = exp.get('details') or exp.get('description', '')
            html += f"<div class='role'><h3>{exp.get('role','')}</h3><p class='company'>{exp.get('company','')} · {period}</p><p>{details}</p></div>"
        html += "</section>"
    if sections['education']:
        html += "<section class='resume-education'><h2>Education</h2>"
        for ed in sections['education']:
            school = ed.get('school') or ed.get('institution', '')
            html += f"<div class='edu'><h3>{ed.get('degree','')}</h3><p class='school'>{school} · {ed.get('year','')}</p></div>"
        html += "</section>"
    # Optional projects section
    projects = sections.get('projects') or []
    if projects:
        html += "<section class='resume-projects'><h2>Projects</h2>"
        for p in projects:
            html += f"<div class='project'><h3>{p.get('title','')}</h3><p>{p.get('description','')}</p></div>"
        html += "</section>"
    html += "</div>"
    return html


def compute_match_score(user_skills: List[str], job_skills_text: str) -> Dict[str, Any]:
    job_skills = normalize_skills(job_skills_text)
    user_set = set([s.lower() for s in user_skills])
    job_set = set(job_skills)
    if not job_set:
        return {'score': 0, 'matching': [], 'missing': []}
    matching = sorted(list(user_set.intersection(job_set)))
    missing = sorted(list(job_set - user_set))
    score = math.floor((len(matching) / len(job_set)) * 100)
    return {'score': score, 'matching': matching, 'missing': missing}


def recommend_jobs_for_user(user, jobs: List[Any], preferences: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    prefs = preferences or {}
    desired_location = (prefs.get('location') or '').lower()
    user_skills = normalize_skills(user.skills or '')
    results = []
    for job in jobs:
        ms = compute_match_score(user_skills, job.required_skills)
        loc_bonus = 5 if desired_location and desired_location in (job.location or '').lower() else 0
        score = min(100, ms['score'] + loc_bonus)
        results.append({
            'job': job,
            'score': score,
            'matching': ms['matching'],
            'missing': ms['missing'],
        })
    # sort by score desc
    return sorted(results, key=lambda r: r['score'], reverse=True)


def score_answer_against_keywords(answer: str, keywords: List[str]) -> Dict[str, Any]:
    if not answer:
        return {'score': 0, 'clarity': 0, 'relevance': 0, 'structure': 0, 'suggestions': ['Provide a complete answer.']}
    a = answer.lower()
    hits = sum([1 for k in keywords if k.lower() in a])
    relevance = min(100, hits * 20)
    clarity = min(100, 30 + len(answer) // 3)
    structure = 50 + (5 if any(x in a for x in ['for example', 'first', 'second']) else 0)
    suggestions = []
    if relevance < 60:
        suggestions.append('Use role-related keywords to increase relevance.')
    if clarity < 60:
        suggestions.append('Add specifics, metrics, and outcomes for clarity.')
    if structure < 60:
        suggestions.append('Organize with STAR: Situation, Task, Action, Result.')
    score = round((relevance + clarity + structure) / 3)
    return {'score': score, 'clarity': clarity, 'relevance': relevance, 'structure': structure, 'suggestions': suggestions}

def predict_career_paths(skills: List[str], years_experience: int = 0) -> List[Dict[str, Any]]:
    """Return a list of possible career paths with probabilities and next steps.
    Designed for unit tests and data APIs.
    """
    skills_norm = [s.lower().strip() for s in skills if s]
    paths: List[Dict[str, Any]] = []
    def prob(base):
        # Simple heuristic factoring experience
        return min(95, base + min(20, years_experience * 5))

    if 'python' in skills_norm and 'sql' in skills_norm:
        paths.append({
            'role': 'Data Engineer',
            'probability': prob(60),
            'next_steps': ['ETL pipelines', 'Cloud data ops', 'SQL mastery']
        })
    if 'python' in skills_norm and ('ml' in skills_norm or 'data analysis' in skills_norm):
        paths.append({
            'role': 'ML Engineer',
            'probability': prob(55),
            'next_steps': ['Model deployment', 'MLOps', 'Experiment tracking']
        })
    if 'javascript' in skills_norm or 'react' in skills_norm:
        paths.append({
            'role': 'Frontend Engineer',
            'probability': prob(50),
            'next_steps': ['Accessibility (WCAG)', 'Performance auditing', 'Design systems']
        })
    if 'sql' in skills_norm and 'data analysis' in skills_norm:
        paths.append({
            'role': 'Data Analyst',
            'probability': prob(65),
            'next_steps': ['Dashboards', 'A/B testing', 'Statistical analysis']
        })
    if not paths:
        paths.append({
            'role': 'Generalist Contributor',
            'probability': prob(40),
            'next_steps': ['Portfolio building', 'Industry networking', 'Core fundamentals']
        })
    return paths


def build_career_plan(skills: List[str]) -> Dict[str, Any]:
    """Return structured plan used by templates: {'paths': [...], 'upskilling': [...]}"""
    skills_norm = [s.lower().strip() for s in skills if s]
    paths = []
    if 'python' in skills_norm:
        paths.append({'role': 'Data Engineer', 'steps': ['ETL pipelines', 'Cloud data ops', 'SQL mastery']})
        paths.append({'role': 'ML Engineer', 'steps': ['Model deployment', 'MLOps', 'Experiment tracking']})
    if 'javascript' in skills_norm or 'react' in skills_norm:
        paths.append({'role': 'Frontend Engineer', 'steps': ['Accessibility (WCAG)', 'Performance auditing', 'Design systems']})
    if 'sql' in skills_norm:
        paths.append({'role': 'Data Analyst', 'steps': ['Dashboards', 'A/B testing', 'Statistical analysis']})
    if not paths:
        paths.append({'role': 'Generalist Contributor', 'steps': ['Portfolio building', 'Industry networking', 'Core fundamentals']})
    upskilling = []
    for s in ['cloud', 'docker', 'security']:
        if s not in skills_norm:
            upskilling.append({'skill': s, 'resource': 'Explore beginner courses and certifications'})
    return {'paths': paths, 'upskilling': upskilling}
