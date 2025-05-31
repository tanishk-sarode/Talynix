import os
import json
import logging
import time
from typing import List, Dict
import requests
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import urllib.parse
import yaml

os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

GLOBAL_COMPANIES = [
    {'name': 'Google', 'careers_url': 'https://careers.google.com/jobs/results/'},
    {'name': 'Microsoft', 'careers_url': 'https://jobs.careers.microsoft.com/global/en/search'},
]
INDIAN_COMPANIES = [
    {'name': 'TCS', 'careers_url': 'https://www.tcs.com/careers'},
    {'name': 'Infosys', 'careers_url': 'https://www.infosys.com/careers/apply.html'},
]

def build_canonical_url(company: str, job_id: str, job_title: str) -> str:
    slug = job_title.lower().replace(' ', '-') if job_title else ''
    if company.lower() == 'microsoft' and job_id:
        return f"https://jobs.careers.microsoft.com/global/en/job/{job_id}/{slug}"
    return ''

def safe_text(element):
    return element.text.strip() if element and hasattr(element, 'text') else ''

# --- Amazon Scraper ---
def fetch_amazon_jobs():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    base_url = "https://www.amazon.jobs/en/search?offset={offset}&result_limit=10&sort=relevant&country[]=IND&industry_experience=less_than_1_year&base_query=Software%20Development%20Engineer"
    driver = webdriver.Chrome(options=opts)
    driver.get(base_url.format(offset=0))
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # Try to get total pages
    try:
        page_buttons = [b for b in soup.findAll() if b.name == 'button' and 'class' in b.attrs and 'page-button' in b['class']]
        total_pages = int(page_buttons[-1].text.strip()) if page_buttons else 1
    except Exception:
        total_pages = 1
    driver.quit()
    jobs = []
    for i in range(total_pages):
        offset = i * 10
        driver = webdriver.Chrome(options=opts)
        driver.get(base_url.format(offset=offset))
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()
        for div in soup.findAll():
            if div.name == 'div' and 'class' in div.attrs and 'job' in div['class']:
                info = None
                for sub in div.findAll():
                    if sub.name == 'div' and 'class' in sub.attrs and 'info' in sub['class']:
                        info = sub
                        break
                title, link, loc, job_id = None, None, None, None
                if info:
                    # Find the <a> inside <h3 class='job-title'>
                    for h3 in info.findAll():
                        if h3.name == 'h3' and 'class' in h3.attrs and 'job-title' in h3['class']:
                            a_tag = None
                            for child in h3.contents:
                                if hasattr(child, 'name') and child.name == 'a' and 'href' in child.attrs:
                                    a_tag = child
                                    break
                            title = a_tag.text.strip() if a_tag and a_tag.text else (h3.text.strip() if h3.text else None)
                            link = "https://www.amazon.jobs" + a_tag['href'] if a_tag and 'href' in a_tag.attrs else None
                    li_tags = [li for li in info.findAll() if li.name == 'li']
                    if len(li_tags) > 0:
                        loc = li_tags[0].text.strip() if li_tags[0].text else None
                    if len(li_tags) > 2:
                        job_id = li_tags[2].text.strip().replace("Job ID: ", "") if li_tags[2].text else None
                posted, quals_text = None, None
                for h2 in div.findAll():
                    if h2.name == 'h2' and 'class' in h2.attrs and 'posting-date' in h2['class']:
                        posted = h2.text.strip().replace("Posted ", "") if h2.text else None
                for sub in div.findAll():
                    if sub.name == 'div' and 'class' in sub.attrs and 'qualifications-preview' in sub['class']:
                        quals_text = sub.text.strip() if sub.text else None
                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company": "Amazon",
                    "location": loc,
                    "posting_date": posted,
                    "work_type": None,
                    "requirements": quals_text,
                    "description": None,
                    "url": link
                })
    return jobs

# --- Microsoft Scraper ---
def fetch_microsoft_jobs():
    url = "https://jobs.careers.microsoft.com/global/en/search?exp=Students%20and%20graduates&el=Bachelors&l=en_us&pg=1&pgSz=20&o=Relevance&flt=true"
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    containers = soup.find_all('div')
    jobs = []
    for job in containers:
        aria_label = job.attrs.get('aria-label', '') if isinstance(job, Tag) else ''
        if not aria_label.startswith('Job item'):
            continue
        title_el = job.find('h2') if isinstance(job, Tag) else None
        title = title_el.text.strip() if isinstance(title_el, Tag) else None
        job_title_slug = title.replace(",", "-").replace(" ", "-") if title else None
        job_id = aria_label.split()[-1] if aria_label else None
        link = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}/{job_title_slug}" if job_id and job_title_slug else None
        # These icons may not always be present, so check for Tag
        date_icon = job.find('i', {'data-icon-name': 'Clock'}) if isinstance(job, Tag) else None
        loc_icon = job.find('i', {'data-icon-name': 'POI'}) if isinstance(job, Tag) else None
        flex_icon = job.find('i', {'data-icon-name': 'AddHome'}) if isinstance(job, Tag) else None
        btn = job.find('button', {'class': 'seeDetailsLink-501'}) if isinstance(job, Tag) else None
        location = loc_icon.find_next_sibling('span').text.strip() if isinstance(loc_icon, Tag) and loc_icon.find_next_sibling('span') else None
        posting_date = date_icon.find_next_sibling('span').text.strip() if isinstance(date_icon, Tag) and date_icon.find_next_sibling('span') else None
        work_type = flex_icon.find_next_sibling('span').text.strip() if isinstance(flex_icon, Tag) and flex_icon.find_next_sibling('span') else None
        description = btn.attrs.get('aria-label') if isinstance(btn, Tag) and 'aria-label' in btn.attrs else None
        jobs.append({
            "job_id": job_id,
            "title": title,
            "company": "Microsoft",
            "location": location,
            "posting_date": posting_date,
            "work_type": work_type,
            "requirements": None,
            "description": description,
            "url": link
        })
    return jobs

# --- Google Scraper ---
def fetch_google_jobs():
    base_url = "https://www.google.com/about/careers/applications/jobs/results"
    config_path = os.path.join(os.path.dirname(__file__), "config/config.yaml")
    if not os.path.exists(config_path):
        locations = ["India", "Netherlands", "Germany", "United Arab Emirates"]
    else:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        locations = config.get("locations", ["India", "Netherlands", "Germany", "United Arab Emirates"])
    skills = ["Python"]
    target_level = ["EARLY"]
    degree = ["BACHELORS"]
    sort_by = "relevance"
    params = []
    for loc in locations[:4]: params.append(("location", loc))
    for skill in skills: params.append(("skills", skill))
    for level in target_level: params.append(("target_level", level))
    for deg in degree: params.append(("degree", deg))
    params.append(("sort_by", sort_by))
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{base_url}?{query}"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    soup = BeautifulSoup(response.text, 'html.parser')
    jobs = []
    for job in soup.find_all("li", {'class': "lLd3Je"}):
        title_el = job.find("h3", {'class': "QJPWVe"}) if isinstance(job, Tag) else None
        loc_el = job.find("span", {'class': "r0wTof"}) if isinstance(job, Tag) else None
        qual_el = job.find("div", {'class': "Xsxa1e"}) if isinstance(job, Tag) else None
        link_el = job.find("a") if isinstance(job, Tag) else None
        job_div = job.find("div", {'jscontroller': "snXUJb"}) if isinstance(job, Tag) else None
        job_id = None
        if isinstance(job_div, Tag) and 'jsdata' in job_div.attrs:
            jsdata = job_div.attrs['jsdata']
            parts = jsdata.split(";")
            if len(parts) >= 2:
                job_id = parts[1]
        if not all([isinstance(title_el, Tag), isinstance(loc_el, Tag), isinstance(qual_el, Tag), isinstance(link_el, Tag)]):
            continue
        jobs.append({
            "job_id": job_id,
            "title": title_el.text.strip(),
            "company": "Google",
            "location": loc_el.text.strip(),
            "posting_date": None,
            "work_type": None,
            "requirements": qual_el.text.strip(),
            "description": None,
            "url": link_el.attrs['href'] if 'href' in link_el.attrs else None
        })
    return jobs

# --- Main Aggregator ---
def fetch_all_jobs():
    jobs = []
    try:
        jobs += fetch_amazon_jobs()
    except Exception as e:
        logging.warning(f"Amazon scraping failed: {e}")
    try:
        jobs += fetch_microsoft_jobs()
    except Exception as e:
        logging.warning(f"Microsoft scraping failed: {e}")
    try:
        jobs += fetch_google_jobs()
    except Exception as e:
        logging.warning(f"Google scraping failed: {e}")
    # Save to jobs_raw.json
    out_path = os.path.join(os.path.dirname(__file__), "storage/jobs_raw.json")
    try:
        with open(out_path, "w") as f:
            json.dump(jobs, f, indent=2)
        logging.info(f"Saved {len(jobs)} jobs to jobs_raw.json.")
    except Exception as e:
        logging.error(f"Failed to save jobs: {e}")
    return jobs

def run_job_scraper():
    return fetch_all_jobs()

if __name__ == "__main__":
    jobs = run_job_scraper()
    print(f"Scraped {len(jobs)} jobs.")
