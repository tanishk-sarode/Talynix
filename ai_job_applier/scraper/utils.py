import requests

def fetch_remoteok_jobs(keyword="python"):
    url = "https://remoteok.com/api"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        jobs = response.json()[1:]  # first item is metadata
        relevant = [job for job in jobs if keyword.lower() in job["position"].lower()]
        return relevant
    else:
        print(f"Error: {response.status_code}")
        return []

# Example
jobs = fetch_remoteok_jobs("flask")
for job in jobs[:3]:
    print(f"{job['company']} - {job['position']} ({job['url']})")
