# Filtering logic module

import json
import logging
from typing import List, Dict, Any
from rapidfuzz import fuzz
import os
from sentence_transformers import SentenceTransformer, util
import numpy as np

os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

JOBS_PATH = 'talynix_project/storage/jobs_raw.json'
FILTERED_JOBS_PATH = 'talynix_project/storage/filtered_jobs.json'
APPLIED_JOBS_PATH = 'talynix_project/storage/applied_jobs.json'

# Load model once (global)
try:
    st_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    st_model = None
    logging.error(f'Could not load SentenceTransformer: {e}')

def compute_semantic_similarity(text1, text2):
    if not st_model or not text1 or not text2:
        return 0.0
    emb1 = st_model.encode(text1, convert_to_tensor=True)
    emb2 = st_model.encode(text2, convert_to_tensor=True)
    return float(util.pytorch_cos_sim(emb1, emb2).item())

# --- Filter 1: Basic Eligibility ---
def filter_eligibility(jobs: List[Dict], user_profile: Dict[str, Any]) -> List[Dict]:
    # Debug mode: skip all eligibility checks, return all jobs
    logging.warning('Debug: Skipping eligibility filters, returning all jobs.')
    return jobs

def relaxed_filter_eligibility(jobs: List[Dict], user_profile: Dict[str, Any]) -> List[Dict]:
    # Only check degree/experience/skills, ignore location and salary
    filtered = []
    user_exp = user_profile.get('min_experience', 0)
    user_degrees = ' '.join(user_profile.get('education', []))
    for job in jobs:
        # Experience filter
        exp_match = True
        for exp_kw in ['year', 'yr', 'experience']:
            if exp_kw in job.get('description', '').lower() or exp_kw in job.get('requirements', '').lower():
                exp_nums = [int(s) for s in job.get('description', '') if s.isdigit()]
                if exp_nums and max(exp_nums) > user_exp + 1:
                    exp_match = False
        # Degree filter
        degree_match = True
        for deg_kw in ['bachelor', 'master', 'phd', 'b.tech', 'm.tech', 'degree', 'certification']:
            if deg_kw in job.get('requirements', '').lower():
                if deg_kw not in user_degrees.lower():
                    degree_match = False
        if exp_match and degree_match:
            filtered.append(job)
    return filtered

# --- Filter 2: Skill-Keyword + Semantic Matching ---
def filter_skill_match(jobs: List[Dict], user_profile: Dict[str, Any], threshold: int = 40) -> List[Dict]:
    filtered = []
    user_skills = user_profile.get('skills', [])
    user_text = ' '.join(user_skills + user_profile.get('education', []))
    for job in jobs:
        job_text = (job.get('requirements') or '') + ' ' + (job.get('description') or '') + ' ' + (job.get('title') or '')
        # Fuzzy skill match (legacy)
        fuzzy_score = 0
        for skill in user_skills:
            if skill and skill.lower() in job_text.lower():
                fuzzy_score += 10
        # Semantic similarity
        semantic_score = compute_semantic_similarity(user_text, job_text)
        # Combine: 70% semantic, 30% fuzzy
        combined_score = 70 * semantic_score + 30 * fuzzy_score
        job['skill_match_pct'] = round(combined_score, 2)
        if job['skill_match_pct'] >= threshold:
            filtered.append(job)
    return filtered

# --- Main Filtering Pipeline ---
def filter_jobs(user_profile: Dict[str, Any], threshold: int = 40) -> List[Dict]:
    try:
        with open(JOBS_PATH, 'r') as f:
            jobs = json.load(f)
    except Exception as e:
        logging.error(f'Could not load jobs: {e}')
        return []
    # Remove already applied jobs
    applied_urls = set()
    if os.path.exists(APPLIED_JOBS_PATH):
        try:
            with open(APPLIED_JOBS_PATH, 'r') as f:
                applied_jobs = json.load(f)
                applied_urls = set(j.get('url') for j in applied_jobs if 'url' in j)
        except Exception as e:
            logging.warning(f'Could not load applied jobs: {e}')
    jobs = [j for j in jobs if j.get('url') not in applied_urls]
    eligible = filter_eligibility(jobs, user_profile)
    skill_filtered = filter_skill_match(eligible, user_profile, threshold)
    # If <10 jobs, fill with relaxed filter (ignore location/salary, but match role/degree/exp/skills)
    if len(skill_filtered) < 10:
        # Find jobs not already in skill_filtered
        filtered_urls = set(j['url'] for j in skill_filtered)
        relaxed_candidates = [j for j in jobs if j.get('url') not in filtered_urls]
        relaxed_eligible = relaxed_filter_eligibility(relaxed_candidates, user_profile)
        relaxed_skill_filtered = filter_skill_match(relaxed_eligible, user_profile, threshold=20)  # Lower threshold for fillers
        # Add up to 10 jobs total
        skill_filtered += relaxed_skill_filtered[:10 - len(skill_filtered)]
    # Rank all jobs by skill_match_pct (descending)
    skill_filtered.sort(key=lambda x: x.get('skill_match_pct', 0), reverse=True)
    top10 = skill_filtered[:10]
    try:
        with open(FILTERED_JOBS_PATH, 'w') as f:
            json.dump(top10, f, indent=2)
        logging.info(f'Saved {len(top10)} filtered jobs.')
    except Exception as e:
        logging.error(f'Could not save filtered jobs: {e}')
    return top10

def evaluate_job_match(user_input: Dict[str, Any], job: Dict[str, Any], company_prestige: Dict[str, int]) -> Dict[str, Any]:
    resume = user_input.get('resume', '')
    # Fix: ensure requirements and description are not None
    requirements = job.get('requirements') or ''
    description = job.get('description') or ''
    job_posting = requirements + ' ' + description
    prefs = user_input.get('user_preferences', {})
    preferred_titles = [t.lower() for t in prefs.get('preferred_titles', [])]
    preferred_locations = [l.lower() for l in prefs.get('location', [])]
    user_exp = prefs.get('experience_years', 0)
    user_job_type = prefs.get('job_type', '').lower()
    # --- Hard Filters ---
    # 1. Experience
    exp_required = 0
    for exp_kw in ['year', 'yr', 'experience']:
        req = job.get('requirements') or ''
        desc = job.get('description') or ''
        text = (req + ' ' + desc).lower()
        if exp_kw in text:
            import re
            found = re.findall(r'(\d+)\s*(?:year|yr)', text)
            if found:
                exp_required = max([int(x) for x in found])
    if exp_required > user_exp + 1:
        return {"eligible": False, "reason": f"Job requires {exp_required} years experience, user has {user_exp}"}
    # 2. Degree/Education
    degree_keywords = ['bachelor', 'master', 'phd', 'b.tech', 'm.tech', 'degree']
    job_degrees = [k for k in degree_keywords if k in job_posting.lower()]
    user_degrees = [k for k in degree_keywords if k in resume.lower()]
    if job_degrees and not any(d in user_degrees for d in job_degrees):
        return {"eligible": False, "reason": "Degree/education mismatch"}
    # 3. Location
    job_loc = (job.get('location', '') or '').lower()
    if not any(loc in job_loc for loc in preferred_locations) and 'remote' not in job_loc:
        return {"eligible": False, "reason": "Location not preferred and not remote"}
    # 4. Job type
    job_type = (job.get('work_type', '') or '').lower()
    if user_job_type and user_job_type not in job_type and job_type:
        return {"eligible": False, "reason": f"Job type mismatch: {job_type}"}
    # --- Soft Scoring ---
    # 1. Skill match (semantic)
    skill_score = int(compute_semantic_similarity(resume, job_posting) * 50)
    # 2. Title similarity
    job_title = (job.get('title', '') or '').lower()
    title_score = max([fuzz.partial_ratio(job_title, t) for t in preferred_titles] + [0]) // 7  # scale to 0-15
    # 3. Location relevance
    location_score = 10 if any(loc in job_loc for loc in preferred_locations) else (5 if 'remote' in job_loc else 0)
    # 4. Recency
    recency_score = 0
    from datetime import datetime, timedelta
    post_date = job.get('posting_date', '')
    try:
        if post_date:
            dt = datetime.strptime(post_date, '%B %d, %Y')
            if dt >= datetime.now() - timedelta(days=14):
                recency_score = 10
            elif dt >= datetime.now() - timedelta(days=30):
                recency_score = 5
    except Exception:
        pass
    # 5. Company prestige
    company_score = company_prestige.get(job.get('company', ''), 5)
    # --- Final Score ---
    match_score = skill_score + title_score + location_score + recency_score + company_score
    comments = []
    if skill_score >= 30:
        comments.append("Strong skill match")
    if title_score >= 10:
        comments.append("Preferred title")
    if location_score >= 10:
        comments.append("Preferred location")
    elif location_score >= 5:
        comments.append("Remote option")
    if recency_score >= 10:
        comments.append("Recent posting")
    if company_score >= 8:
        comments.append("Prestigious company")
    return {
        "eligible": True,
        "match_score": match_score,
        "score_breakdown": {
            "skill_match": skill_score,
            "title_match": title_score,
            "location_score": location_score,
            "recency_score": recency_score,
            "company_score": company_score
        },
        "comments": ", ".join(comments)
    }

def match_and_rank_jobs(user_input: Dict[str, Any], jobs: List[Dict], company_prestige: Dict[str, int]) -> List[Dict]:
    results = []
    for job in jobs:
        result = evaluate_job_match(user_input, job, company_prestige)
        if result.get('eligible') and result.get('match_score', 0) >= 40:
            job_result = job.copy()
            job_result.update(result)
            results.append(job_result)
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:10]

def filter_eligible_jobs(user_input: Dict[str, Any], jobs: List[Dict], company_prestige: Dict[str, int]) -> List[Dict]:
    eligible_jobs = []
    for job in jobs:
        result = evaluate_job_match(user_input, job, company_prestige)
        if result.get('eligible'):
            job_result = job.copy()
            job_result.update(result)
            eligible_jobs.append(job_result)
    return eligible_jobs

# --- Main Filtering and Ranking Pipeline ---
def filter_and_rank_jobs(user_input: Dict[str, Any], jobs: List[Dict], company_prestige: Dict[str, int]) -> List[Dict]:
    # 1. Hard filter: only eligible jobs
    eligible_jobs = filter_eligible_jobs(user_input, jobs, company_prestige)
    # 2. Soft filter: only jobs with match_score >= 40, ranked by match_score
    ranked = [j for j in eligible_jobs if j.get('match_score', 0) >= 40]
    ranked.sort(key=lambda x: x['match_score'], reverse=True)
    return ranked[:10]

if __name__ == '__main__':
    # Example usage for new pipeline
    import sys
    # Load user input (resume, preferences)
    with open('talynix_project/storage/user_prefs.json') as f:
        user_prefs = json.load(f)
    # You may want to load resume text from a file or user input
    resume_text = ''
    try:
        with open('talynix_project/storage/resume_data.json') as f:
            resume_json = json.load(f)
            resume_text = resume_json.get('raw_text', '')
    except Exception:
        pass
    user_input = {
        'resume': resume_text,
        'job_posting': '',  # Not used here
        'user_preferences': {
            'preferred_titles': user_prefs.get('target_roles', []),
            'location': user_prefs.get('preferred_locations', []),
            'experience_years': user_prefs.get('min_experience', 0),
            'job_type': 'Full-time'  # You can make this dynamic
        }
    }
    # Load jobs
    with open('talynix_project/storage/jobs_raw.json') as f:
        jobs = json.load(f)
    # Example company prestige mapping
    company_prestige = { 'Google': 10, 'Microsoft': 9, 'Amazon': 8 }
    # Run new pipeline
    top_jobs = filter_and_rank_jobs(user_input, jobs, company_prestige)
    # Save to both filtered_jobs.json and top10_jobs.json
    with open('talynix_project/storage/filtered_jobs.json', 'w') as f:
        json.dump(top_jobs, f, indent=2)
    with open('talynix_project/storage/top10_jobs.json', 'w') as f:
        json.dump(top_jobs, f, indent=2)
    print(json.dumps(top_jobs, indent=2))
