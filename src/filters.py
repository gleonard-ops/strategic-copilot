from datetime import datetime, timedelta
import re

# US state names and abbreviations (used for allow-list matching in "us only" mode)
_US_STATES_FULL = [
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut',
    'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa',
    'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan',
    'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina',
    'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania', 'rhode island',
    'south carolina', 'south dakota', 'tennessee', 'texas', 'utah', 'vermont',
    'virginia', 'washington', 'west virginia', 'wisconsin', 'wyoming',
    'district of columbia',
]

_US_STATES_ABBR = [
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id', 'il', 'in',
    'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv',
    'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 'sd', 'tn',
    'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc',
]

_US_COUNTRY_TERMS = [
    'united states', 'usa', 'u.s.a', 'u.s.', ' us,', ' us -', '- us', ', us',
]


def _location_ok(loc: str, mode: str) -> bool:
    if not loc:
        return True
    loc_lower = loc.strip().lower()

    if mode == 'remote only':
        return 'remote' in loc_lower

    if mode == 'us only':
        # Full state names and country terms — safe as plain substring matches
        if any(state in loc_lower for state in _US_STATES_FULL):
            return True
        if any(term in loc_lower for term in _US_COUNTRY_TERMS):
            return True

        # Two-letter abbreviations need word-boundary matching so "CA" doesn't
        # match inside unrelated words like "Canada"
        for abbr in _US_STATES_ABBR:
            if re.search(rf'\b{abbr}\b', loc_lower):
                return True

        # Bare "remote" with no location detail at all — ambiguous, allow it
        # rather than silently drop postings that never named a country
        if loc_lower.strip() == 'remote':
            return True

        return False

    # "any" or anything else — no filtering
    return True


# Fallback defaults used when profile fields are blank
_DEFAULT_SENIORITY = [
    'head of', 'vp ', 'vp,', 'vice president', 'director', 'chief',
    'principal', 'managing director', 'general manager',
]
_DEFAULT_TARGET = [
    'gtm', 'go-to-market', 'go to market', 'sales', 'revenue', 'commercial',
    'product ops', 'product operations', 'product strategy', 'business ops',
    'business operations', 'operations', ' ops', 'strategy', 'strategic',
    'transformation', 'enablement', 'customer success', 'customer experience',
    'partnerships', 'alliances', 'biz dev', 'ai strategy', 'ai lead', 'enterprise',
    'growth', 'chief of staff', 'value', 'market', 'field ',
]
_DEFAULT_EXCLUDE = [
    'engineer', 'devops', 'backend', 'frontend', 'fullstack', 'full-stack', 'qa ', 'sre ',
    'design', 'scientist', 'researcher', ' research', ' legal', 'counsel', 'attorney',
    'compliance', 'governance', 'regulatory', 'finance', 'financial', 'treasury',
    'accounting', 'controllership', 'procurement', 'tax ', 'compensation', 'benefits',
    'recruiter', 'recruiting', 'talent acquisition', 'brand ', 'content director',
    'creative director', 'communications', 'public relation', 'cybersecurity',
    'information security', 'security operation', 'supply chain', 'logistics',
    'facilities', 'real estate', 'data science', 'machine learning', 'clinical', 'medical',
]


def _parse_list(value: str) -> list:
    """Parse a comma-separated or pipe-separated string into a list of lowercase strings."""
    if not value or not value.strip():
        return []
    sep = '|' if '|' in value else ','
    return [item.strip().lower() for item in value.split(sep) if item.strip()]


def _build_filter_lists(profile: dict) -> tuple:
    """Return (location_mode, seniority, target, exclude) from profile, with defaults."""
    location = (profile.get('location') or '').strip().lower() or 'us only'
    seniority = _parse_list(profile.get('seniority_keywords', '')) or _DEFAULT_SENIORITY
    target    = _parse_list(profile.get('target_functions', ''))   or _DEFAULT_TARGET
    exclude   = _parse_list(profile.get('exclude_functions', ''))  or _DEFAULT_EXCLUDE
    return location, seniority, target, exclude


def is_too_old(job: dict, days: int = 30) -> bool:
    date_str = (job.get('date_posted') or '')[:10]
    if not date_str:
        return False
    try:
        return datetime.strptime(date_str, '%Y-%m-%d') < datetime.utcnow() - timedelta(days=days)
    except ValueError:
        return False



def passes_title_filter(job: dict, profile: dict = None) -> bool:
    profile  = profile or {}
    location, seniority, target, exclude = _build_filter_lists(profile)

    title = (job.get('job_title') or '').lower()
    loc   = (job.get('location_raw') or '').strip()

    if not _location_ok(loc, location):
        return False

    has_seniority = any(s in title for s in seniority)
    has_exclude   = any(s in title for s in exclude)
    has_target    = any(f in title for f in target)

    return has_seniority and not has_exclude and has_target
