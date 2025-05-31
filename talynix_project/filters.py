# Filtering logic module

import json
import logging
from typing import List, Dict, Any
from rapidfuzz import fuzz
import os

os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

JOBS_PATH = 'talynix_project/storage/jobs_raw.json'
FILTERED_JOBS_PATH = 'talynix_project/storage/filtered_jobs.json'
APPLIED_JOBS_PATH = 'talynix_project/storage/applied_jobs.json'

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

# --- Filter 2: Skill-Keyword Matching ---
def filter_skill_match(jobs: List[Dict], user_profile: Dict[str, Any], threshold: int = 40) -> List[Dict]:
    # Debug mode: skip skill matching, return all jobs
    logging.warning('Debug: Skipping skill match filter, returning all jobs.')
    for job in jobs:
        job['skill_match_pct'] = 100
    return jobs

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

if __name__ == '__main__':
    from user_extractor import get_user_profile
    profile = get_user_profile()
    filtered = filter_jobs(profile)
    print(f'{len(filtered)} jobs after filtering.')
