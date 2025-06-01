import streamlit as st
import os
import json
from resume_parser import parse_resume
from user_extractor import set_user_prefs, load_user_prefs, get_user_profile
from job_scraper import run_job_scraper
from filters import filter_and_rank_jobs, evaluate_job_match

STORAGE = 'talynix_project/storage/'

st.set_page_config(page_title='Talynix AI Job Application Assistant', layout='wide')
st.title('Talynix AI Job Application Assistant')

# --- Tab 1: Upload Resume ---
with st.sidebar:
    st.header('Navigation')
    tab = st.radio('Go to:', ['Upload Resume', 'Set Preferences', 'Fetch & Filter Jobs', 'My Applications'])

if tab == 'Upload Resume':
    st.header('Upload Resume')
    resume_json_path = os.path.join(STORAGE, 'resume_data.json')
    data = None
    if os.path.exists(resume_json_path):
        with open(resume_json_path) as f:
            try:
                data = json.load(f)
            except Exception:
                data = None
    uploaded = st.file_uploader('Upload your resume (PDF or DOCX)', type=['pdf', 'docx'])
    if uploaded:
        os.makedirs(STORAGE, exist_ok=True)
        file_path = os.path.join(STORAGE, 'uploaded_resume.' + uploaded.name.split('.')[-1])
        with open(file_path, 'wb') as f:
            f.write(uploaded.read())
        if st.button('Parse Resume'):
            try:
                data = parse_resume(file_path)
                st.success('Resume parsed successfully!')
            except Exception as e:
                st.error(f'Failed to parse resume: {e}')
    # Always show the editable form if data exists
    if data:
        st.warning('Please carefully review and correct the parsed fields below. The parser may not always extract everything perfectly!')
        with st.form("confirm_resume"):
            name = st.text_input("Name", value=data.get("name", ""))
            email = st.text_input("Email", value=data.get("email", ""))
            phone = st.text_input("Phone", value=data.get("phone", ""))
            education = st.text_area("Education", value="\n".join(data.get("education", [])))
            experience = st.text_area("Experience", value="\n".join(data.get("experience", [])))
            skills = st.text_area("Skills", value=", ".join(data.get("skills", [])))
            projects = st.text_area("Projects", value="\n".join(data.get("projects", [])))
            certifications = st.text_area("Certifications", value="\n".join(data.get("certifications", [])))
            submitted = st.form_submit_button("Confirm & Save")
            if submitted:
                corrected = {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "education": [e.strip() for e in education.splitlines() if e.strip()],
                    "experience": [e.strip() for e in experience.splitlines() if e.strip()],
                    "skills": [s.strip() for s in skills.split(",") if s.strip()],
                    "projects": [p.strip() for p in projects.splitlines() if p.strip()],
                    "certifications": [c.strip() for c in certifications.splitlines() if c.strip()],
                    "raw_text": data.get("raw_text", "")
                }
                with open(resume_json_path, 'w') as f:
                    json.dump(corrected, f, indent=2)
                st.success("Resume data saved and confirmed!")

# --- Tab 2: Set Preferences ---
elif tab == 'Set Preferences':
    st.header('Set Your Job Preferences')
    prefs = load_user_prefs()
    resume_json_path = os.path.join(STORAGE, 'resume_data.json')
    resume_data = None
    if os.path.exists(resume_json_path):
        with open(resume_json_path) as f:
            try:
                resume_data = json.load(f)
            except Exception:
                resume_data = None
    # Smart default locations and roles
    default_locations = [
        "Bangalore", "Hyderabad", "Pune", "Mumbai", "Delhi", "Chennai", "Gurgaon", "Noida", "Remote", "India",
        "San Francisco", "Seattle", "New York", "London", "Berlin", "Singapore", "Toronto", "Sydney", "Dublin"
    ]
    default_roles = [
        "Software Engineer", "Data Scientist", "AI Engineer", "ML Engineer", "Backend Developer", "Frontend Developer",
        "Full Stack Developer", "DevOps Engineer", "Product Manager", "Research Scientist", "SDE", "Intern"
    ]
    # If user has not set preferences, use defaults
    user_locations = prefs.get('preferred_locations')
    user_roles = prefs.get('target_roles')
    if not user_locations or len(user_locations) == 0:
        user_locations = default_locations
    if not user_roles or len(user_roles) == 0:
        user_roles = default_roles
    locations = st.text_input(
        'Preferred Locations (comma separated)',
        ', '.join(user_locations),
        help='Suggestions: ' + ', '.join(default_locations[:8])
    )
    roles = st.text_input(
        'Target Roles (comma separated)',
        ', '.join(user_roles),
        help='Suggestions: ' + ', '.join(default_roles[:8])
    )
    min_exp = st.number_input('Minimum Experience (years)', min_value=0, value=prefs.get('min_experience', 0))
    salary = st.text_input('Desired Salary Range (optional)', prefs.get('salary_range', ''))
    notice = st.text_input('Notice Period / Join Timeline (optional)', prefs.get('notice_period', ''))
    company_pref = st.selectbox('Company Preference', ['Global > Indian', 'Indian > Global'],
                                index=0 if 'Global' in prefs.get('company_preference', '') else 1)
    if st.button('Save Preferences'):
        set_user_prefs(
            preferred_locations=[l.strip() for l in locations.split(',') if l.strip()],
            target_roles=[r.strip() for r in roles.split(',') if r.strip()],
            min_experience=min_exp,
            salary_range=salary,
            notice_period=notice,
            company_preference=company_pref
        )
        st.success('Preferences saved!')

# --- Tab 3: Fetch & Filter Jobs ---
elif tab == 'Fetch & Filter Jobs':
    st.header('Fetch & Filter Jobs')
    # Resume preview/download
    resume_json_path = os.path.join(STORAGE, 'resume_data.json')
    if os.path.exists(resume_json_path):
        with open(resume_json_path) as f:
            resume_data = json.load(f)
        st.subheader('Resume Preview')
        st.write(resume_data.get('raw_text', '')[:1000] + '...')
        st.download_button('Download Resume JSON', json.dumps(resume_data, indent=2), file_name='resume_data.json')
    # Show ineligible jobs with reasons
    show_ineligible = st.checkbox('Show ineligible jobs with reasons', value=False)
    # Filters/sorting
    sort_by = st.selectbox('Sort jobs by', ['match_score', 'company', 'location'])
    filter_company = st.text_input('Filter by company (optional)').strip().lower()
    filter_location = st.text_input('Filter by location (optional)').strip().lower()
    if st.button('Run Job Scraper & Filter → Get Top 10 Recommendations'):
        with st.spinner('Filtering jobs...'):
            with open(os.path.join(STORAGE, 'user_prefs.json')) as f:
                user_prefs = json.load(f)
            resume_text = ''
            try:
                with open(os.path.join(STORAGE, 'resume_data.json')) as f:
                    resume_json = json.load(f)
                    resume_text = resume_json.get('raw_text', '')
            except Exception:
                pass
            user_input = {
                'resume': resume_text,
                'job_posting': '',
                'user_preferences': {
                    'preferred_titles': user_prefs.get('target_roles', []),
                    'location': user_prefs.get('preferred_locations', []),
                    'experience_years': user_prefs.get('min_experience', 0),
                    'job_type': 'Full-time'
                }
            }
            with open(os.path.join(STORAGE, 'jobs_raw.json')) as f:
                jobs = json.load(f)
            # Deduplicate jobs by url
            seen = set()
            deduped_jobs = []
            for job in jobs:
                url = job.get('url')
                if url and url not in seen:
                    seen.add(url)
                    deduped_jobs.append(job)
            company_prestige = { 'Google': 10, 'Microsoft': 9, 'Amazon': 8 }
            top10 = filter_and_rank_jobs(user_input, deduped_jobs, company_prestige)
            # Also get ineligible jobs with reasons
            ineligible = []
            for job in deduped_jobs:
                result = evaluate_job_match(user_input, job, company_prestige)
                if not result.get('eligible'):
                    job_copy = job.copy()
                    job_copy['reason'] = result.get('reason', 'Not eligible')
                    ineligible.append(job_copy)
            with open(os.path.join(STORAGE, 'filtered_jobs.json'), 'w') as f:
                json.dump(top10, f, indent=2)
            with open(os.path.join(STORAGE, 'top10_jobs.json'), 'w') as f:
                json.dump(top10, f, indent=2)
            with open(os.path.join(STORAGE, 'ineligible_jobs.json'), 'w') as f:
                json.dump(ineligible, f, indent=2)
        st.success('Top 10 jobs ready!')
        # Filters/sorting for display
        jobs = top10
        if filter_company:
            jobs = [j for j in jobs if filter_company in j.get('company', '').lower()]
        if filter_location:
            jobs = [j for j in jobs if filter_location in j.get('location', '').lower()]
        if sort_by == 'company':
            jobs = sorted(jobs, key=lambda x: x.get('company', ''))
        elif sort_by == 'location':
            jobs = sorted(jobs, key=lambda x: x.get('location', ''))
        else:
            jobs = sorted(jobs, key=lambda x: x.get('match_score', 0), reverse=True)
        st.subheader('Top 10 Recommended Jobs')
        for i, job in enumerate(jobs, 1):
            with st.expander(f"{i}. {job['title']} at {job['company']}"):
                st.markdown(f"**[{job['title']}]({job['url']}) at {job['company']}**")
                st.write(f"Location: {job['location']} | Score: {job.get('match_score', '-')}")
                st.write('**Score breakdown:**', job.get('score_breakdown', {}))
                st.write('**Why this job?**', job.get('comments', ''))
                desc = job['description'] if job['description'] else job.get('requirements', '')
                if desc:
                    st.write(desc[:300] + '...')
                else:
                    st.write('(No description available)')
                col1, col2, col3 = st.columns(3)
                with col1:
                    url = job['url'] if job['url'] else None
                    if url and isinstance(url, str):
                        st.link_button('Apply Now', url)
                    else:
                        st.write(':red[No application link available]')
                with col2:
                    if st.button(f'Not Interested {i}'):
                        if jobs and i-1 < len(jobs):
                            jobs.pop(i-1)
                            with open(os.path.join(STORAGE, 'top10_jobs.json'), 'w') as f:
                                json.dump(jobs, f, indent=2)
                            st.rerun()
                with col3:
                    if st.button(f'Mark as Applied {i}'):
                        applied_path = os.path.join(STORAGE, 'applied_jobs.json')
                        applied = []
                        if os.path.exists(applied_path):
                            with open(applied_path) as f:
                                applied = json.load(f)
                        if not any(j.get('url') == job.get('url') for j in applied):
                            applied.append(job)
                            with open(applied_path, 'w') as f:
                                json.dump(applied, f, indent=2)
                            st.success('Marked as applied!')
        # Show ineligible jobs with reasons
        if show_ineligible:
            st.subheader('Ineligible Jobs (with reasons)')
            with open(os.path.join(STORAGE, 'ineligible_jobs.json')) as f:
                ineligible = json.load(f)
            for job in ineligible[:10]:
                st.markdown(f"- **{job['title']}** at {job['company']} | {job.get('reason', '')}")

# --- Tab 4: My Applications ---
elif tab == 'My Applications':
    st.header('My Applications')
    applied_path = os.path.join(STORAGE, 'applied_jobs.json')
    applied = []
    if os.path.exists(applied_path):
        with open(applied_path) as f:
            applied = json.load(f)
    st.subheader('Applied Jobs Log')
    st.write(f"Total: {len(applied)}")
    for job in applied:
        st.markdown(f"- [{job.get('title', 'Job')}]({job.get('url', '')}) at {job.get('company', '')}")
    st.subheader('Import Applied Jobs')
    uploaded = st.file_uploader('Upload CSV of applied job URLs', type=['csv'], key='applied')
    if uploaded:
        import pandas as pd
        df = pd.read_csv(uploaded)
        for url in df.iloc[:,0]:
            if not any(j.get('url') == url for j in applied):
                applied.append({'url': url})
        with open(applied_path, 'w') as f:
            json.dump(applied, f, indent=2)
        st.success('Applied jobs imported!')
    manual = st.text_area('Paste applied job URLs (one per line)')
    if st.button('Add URLs'):
        for url in manual.splitlines():
            url = url.strip()
            if url and not any(j.get('url') == url for j in applied):
                applied.append({'url': url})
        with open(applied_path, 'w') as f:
            json.dump(applied, f, indent=2)
        st.success('Added!')
