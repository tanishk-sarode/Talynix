import json
import logging
from typing import Dict, Any, List
import os

os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

USER_PREFS_PATH = 'talynix_project/storage/user_prefs.json'
RESUME_DATA_PATH = 'talynix_project/storage/resume_data.json'

def get_default_prefs() -> Dict[str, Any]:
    return {
        'preferred_locations': [],
        'target_roles': [],
        'min_experience': 0,
        'salary_range': '',
        'notice_period': '',
        'company_preference': 'Global > Indian',
    }

def save_user_prefs(prefs: Dict[str, Any]):
    try:
        with open(USER_PREFS_PATH, 'w') as f:
            json.dump(prefs, f, indent=2)
        logging.info('User preferences saved.')
    except Exception as e:
        logging.error(f'Failed to save user preferences: {e}')

def load_user_prefs() -> Dict[str, Any]:
    if os.path.exists(USER_PREFS_PATH):
        try:
            with open(USER_PREFS_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f'Could not load user preferences: {e}')
    return get_default_prefs()

def set_user_prefs(
    preferred_locations=None,
    target_roles=None,
    min_experience=None,
    salary_range=None,
    notice_period=None,
    company_preference=None
):
    prefs = load_user_prefs()
    if preferred_locations is not None:
        prefs['preferred_locations'] = preferred_locations
    if target_roles is not None:
        prefs['target_roles'] = target_roles
    if min_experience is not None:
        prefs['min_experience'] = min_experience
    if salary_range is not None:
        prefs['salary_range'] = salary_range
    if notice_period is not None:
        prefs['notice_period'] = notice_period
    if company_preference is not None:
        prefs['company_preference'] = company_preference
    save_user_prefs(prefs)
    return prefs

def get_user_profile() -> Dict[str, Any]:
    """
    Combines parsed resume data and user preferences into a unified user profile JSON.
    """
    prefs = load_user_prefs()
    try:
        with open(RESUME_DATA_PATH, 'r') as f:
            resume = json.load(f)
    except Exception as e:
        logging.warning(f'Could not load resume data: {e}')
        resume = {}
    profile = {
        'name': resume.get('name', ''),
        'email': resume.get('email', ''),
        'phone': resume.get('phone', ''),
        'education': resume.get('education', []),
        'experience': resume.get('experience', []),
        'skills': resume.get('skills', []),
        'projects': resume.get('projects', []),
        'certifications': resume.get('certifications', []),
        'preferred_locations': prefs.get('preferred_locations', []),
        'target_roles': prefs.get('target_roles', []),
        'min_experience': prefs.get('min_experience', 0),
        'salary_range': prefs.get('salary_range', ''),
        'notice_period': prefs.get('notice_period', ''),
        'company_preference': prefs.get('company_preference', 'Global > Indian'),
    }
    return profile

if __name__ == '__main__':
    # Example usage
    prefs = set_user_prefs(
        preferred_locations=['Bangalore', 'Remote – India'],
        target_roles=['Software Engineer', 'Data Scientist'],
        min_experience=2,
        salary_range='20-30 LPA',
        notice_period='Immediate',
        company_preference='Global > Indian'
    )
    print(json.dumps(prefs, indent=2))
