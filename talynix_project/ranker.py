import json
import logging
from typing import List, Dict, Any
import os
from datetime import datetime, timedelta


os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')



FILTERED_JOBS_PATH = 'talynix_project/storage/filtered_jobs.json'
APPLIED_JOBS_PATH = 'talynix_project/storage/applied_jobs.json'


# --- Ranking Logic ---
def compute_relevance_score(job: Dict[str, Any], user_profile: Dict[str, Any], company_rank: Dict[str, int]) -> float:
    # 1. Skill match percentage (50%)
    skill_score = job.get('skill_match_pct', 0)
    skill_weight = 0.5
    # 2. Location preference match (20% exact, 10% state, 5% remote)
    user_locs = [l.lower() for l in user_profile.get('preferred_locations', [])]
    job_loc = job.get('location', '').lower()
    loc_score = 0
    for loc in user_locs:
        if loc in job_loc:
            loc_score = 20
            break
        elif loc.split(',')[0] in job_loc:
            loc_score = 10
    if 'remote' in job_loc:
        loc_score = max(loc_score, 5)
    loc_weight = 0.2
    # 3. Company preference ranking (10%)
    company = job.get('company', '')
    company_score = company_rank.get(company, 0)
    company_weight = 0.1
    # 4. Posting recency (10%)
    recency_score = 0
    post_date = job.get('posting_date', '')
    try:
        if post_date:
            dt = datetime.strptime(post_date, '%Y-%m-%d')
            if dt >= datetime.now() - timedelta(days=7):
                recency_score = 10
    except Exception:
        pass
    recency_weight = 0.1
    # 5. Not applied (already filtered)
    # Composite score
    score = (
        skill_score * skill_weight +
        loc_score * loc_weight +
        company_score * company_weight +
        recency_score * recency_weight
    )
    job['relevance_score'] = round(score, 2)
    return job['relevance_score']

def get_company_rank(user_profile: Dict[str, Any]) -> Dict[str, int]:
    # Assign company preference weights
    pref = user_profile.get('company_preference', 'Global > Indian')
    global_weight = 10 if 'global' in pref.lower() else 5
    indian_weight = 10 if 'indian' in pref.lower() else 5
    # Example: assign based on company list
    from job_scraper import GLOBAL_COMPANIES, INDIAN_COMPANIES
    rank = {}
    for c in GLOBAL_COMPANIES:
        rank[c['name']] = global_weight
    for c in INDIAN_COMPANIES:
        rank[c['name']] = indian_weight
    return rank

def rank_jobs(user_profile: Dict[str, Any], top_n: int = 10) -> List[Dict]:
    try:
        with open(FILTERED_JOBS_PATH, 'r') as f:
            jobs = json.load(f)
    except Exception as e:
        logging.error(f'Could not load filtered jobs: {e}')
        return []
    company_rank = get_company_rank(user_profile)
    for job in jobs:
        compute_relevance_score(job, user_profile, company_rank)
    jobs = sorted(jobs, key=lambda x: x.get('relevance_score', 0), reverse=True)
    top_jobs = jobs[:top_n]
    # Save top jobs for UI
    try:
        with open('talynix_project/storage/top10_jobs.json', 'w') as f:
            json.dump(top_jobs, f, indent=2)
    except Exception as e:
        logging.warning(f'Could not save top10 jobs: {e}')
    return top_jobs

if __name__ == '__main__':
    from user_extractor import get_user_profile
    profile = get_user_profile()
    top10 = rank_jobs(profile)
    print(json.dumps(top10, indent=2))

