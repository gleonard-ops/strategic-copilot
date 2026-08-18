import re
import time
import requests
from datetime import datetime


def _strip_html(html: str) -> str:
    if not html:
        return ''
    text = re.sub(r'<[^>]+>', ' ', html)
    for entity, char in [('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"')]:
        text = text.replace(entity, char)
    return re.sub(r'\s+', ' ', text).strip()[:8000]


def _get(url: str):
    try:
        resp = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f'    HTTP error fetching {url}: {e}')
        return None


def fetch_ashby(handle: str, company_name: str) -> list:
    data = _get(f'https://api.ashbyhq.com/posting-api/job-board/{handle}?includeCompensation=true')
    if not data:
        return []
    jobs = []
    for item in data.get('jobs', []):
        loc = item.get('location') or {}
        jobs.append({
            'job_title':     item.get('title', ''),
            'company':       company_name,
            'job_url':       item.get('jobUrl', ''),
            'description':   (item.get('descriptionPlain') or _strip_html(item.get('descriptionHtml', '')))[:8000],
            'date_posted':   (item.get('publishedAt') or '')[:10],
            'location_raw':  loc.get('name', '') if isinstance(loc, dict) else str(loc),
        })
    return jobs


def fetch_greenhouse(handle: str, company_name: str) -> list:
    data = _get(f'https://boards-api.greenhouse.io/v1/boards/{handle}/jobs?content=true')
    if not data:
        return []
    jobs = []
    for item in data.get('jobs', []):
        loc = item.get('location') or {}
        jobs.append({
            'job_title':    item.get('title', ''),
            'company':      company_name,
            'job_url':      item.get('absolute_url', ''),
            'description':  _strip_html(item.get('content', ''))[:8000],
            'date_posted':  (item.get('updated_at') or '')[:10],
            'location_raw': loc.get('name', '') if isinstance(loc, dict) else str(loc),
        })
    return jobs


def fetch_lever(handle: str, company_name: str) -> list:
    data = _get(f'https://api.lever.co/v0/postings/{handle}?mode=json')
    if not isinstance(data, list):
        return []
    jobs = []
    for item in data:
        created_ms = item.get('createdAt', 0) or 0
        date_posted = datetime.utcfromtimestamp(created_ms / 1000).strftime('%Y-%m-%d') if created_ms else ''
        cats = item.get('categories') or {}
        jobs.append({
            'job_title':    item.get('text', ''),
            'company':      company_name,
            'job_url':      item.get('hostedUrl', ''),
            'description':  _strip_html(item.get('descriptionPlain') or item.get('description', ''))[:8000],
            'date_posted':  date_posted,
            'location_raw': cats.get('location', '') if isinstance(cats, dict) else '',
        })
    return jobs


def fetch_gem(handle: str, company_name: str) -> list:
    data = _get(f'https://api.gem.com/job_board/v0/{handle}/job_posts/')
    if not isinstance(data, list):
        return []
    jobs = []
    for item in data:
        loc = item.get('location') or {}
        jobs.append({
            'job_title':    item.get('title', ''),
            'company':      company_name,
            'job_url':      item.get('absolute_url', ''),
            'description':  (item.get('content_plain') or _strip_html(item.get('content', '')))[:8000],
            'date_posted':  (item.get('first_published_at') or '')[:10],
            'location_raw': loc.get('name', '') if isinstance(loc, dict) else str(loc),
        })
    return jobs


def fetch_workday(handle: str, company_name: str, seniority_keywords: list = None) -> list:
    if '/' not in handle:
        print(f'    Workday handle must be "subdomain.wdN/board", got: {handle}')
        return []

    tenant_domain, board = handle.split('/', 1)
    company_slug = tenant_domain.split('.')[0]
    base = f'https://{tenant_domain}.myworkdayjobs.com'
    api  = f'{base}/wday/cxs/{company_slug}/{board}'

    _default = ['VP', 'Director', 'Head of', 'Vice President', 'Senior Director']
    terms = [t.lower() for t in (seniority_keywords or _default)]

    # Workday's searchText OR-syntax is parsed inconsistently across tenants
    # (some tenants return 0 results for a boolean query that others handle fine).
    # Pull everything with an empty search and filter client-side instead —
    # slower per-company but correct on every tenant.
    listings = []
    offset, limit = 0, 20
    dumped_sample = False
    while True:
        try:
            resp = requests.post(
                f'{api}/jobs',
                json={'limit': limit, 'offset': offset, 'searchText': '', 'appliedFacets': {}},
                headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f'    Workday listing error for {company_name}: {e}')
            break

        batch = data.get('jobPostings', [])
        if not batch:
            break

        # DIAGNOSTIC: dump full shape of the first posting once per company
        if not dumped_sample:
            import json
            print(f'    [{company_name}] SAMPLE POSTING KEYS: {list(batch[0].keys())}')
            print(f'    [{company_name}] SAMPLE POSTING FULL: {json.dumps(batch[0])[:2000]}')
            dumped_sample = True

        listings.extend(batch)
        total = data.get('total', 0)
        offset += limit
        if offset >= total or offset >= 400:  # raised cap since we're no longer pre-filtered
            break
        time.sleep(0.3)

    # Client-side keyword filter on title (mirrors old searchText intent)
    filtered = [
        p for p in listings
        if any(term in (p.get('title') or '').lower() for term in terms)
    ]

    jobs = []
    for posting in filtered:
        ext_path = posting.get('externalPath', '')
        if not ext_path:
            continue
        try:
            detail_resp = requests.get(
                f'{api}{ext_path}',
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=30,
            )
            detail_resp.raise_for_status()
            info = detail_resp.json().get('jobPostingInfo', {})
        except Exception:
            info = {}

        job_url = f'{base}/en-US/{board}{ext_path}'
        jobs.append({
            'job_title':    info.get('title') or posting.get('title', ''),
            'company':      company_name,
            'job_url':      job_url,
            'description':  _strip_html(info.get('jobDescription', ''))[:8000],
            'date_posted':  (info.get('startDate') or '')[:10],
            'location_raw': posting.get('locationsText', ''),
        })
        time.sleep(0.2)

    return jobs
    
FETCHERS = {
    'ashby':      fetch_ashby,
    'greenhouse': fetch_greenhouse,
    'lever':      fetch_lever,
    'gem':        fetch_gem,
    'workday':    fetch_workday,
}
