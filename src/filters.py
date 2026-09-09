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

_NON_US_COUNTRY_TERMS = [
    'canada', 'mexico', 'india', 'united kingdom', 'uk', 'australia',
    'singapore', 'germany', 'france', 'ireland', 'philippines', 'brazil',
    'japan', 'china', 'poland', 'spain', 'netherlands',
]

# Some ATS location fields use the ISO country code "IN" for India instead of
# spelling the country out (e.g. "Bangalore, IN"), which is indistinguishable
# from the Indiana state abbreviation by the country/state terms above and
# falls through to the ambiguous two-letter abbreviation match below,
# incorrectly passing as US. Catch it earlier via known Indian city names,
# so e.g. "Bangalore, IN" is excluded while "Indianapolis, IN" still passes.
_INDIA_CITY_TERMS = [
    'bangalore', 'bengaluru', 'mumbai', 'new delhi', 'delhi', 'hyderabad',
    'pune', 'chennai', 'gurgaon', 'gurugram', 'noida', 'kolkata',
    'ahmedabad', 'jaipur', 'kochi', 'coimbatore', 'chandigarh', 'mysore',
    'mysuru', 'trivandrum', 'thiruvananthapuram', 'vadodara', 'nagpur',
]


def _location_ok(loc: str, mode: str) -> bool:
    if not loc:
        return True
    loc_lower = loc.strip().lower()

    if mode == 'remote only':
        return 'remote' in loc_lower

    if mode == 'us only':
         # A named non-US country anywhere in the string overrides any
        # ambiguous 2-letter code match (e.g. "CA" = Canada, not California)
        if any(re.search(rf'\b{re.escape(country)}\b', loc_lower) for country in _NON_US_COUNTRY_TERMS):
            return False

        # Same idea for India specifically: some ATS fields give the ISO
        # country code "IN" rather than spelling out "India", which the
        # check above won't catch. A known Indian city name is a reliable
        # tell that this is NOT the Indiana abbreviation.
        if any(re.search(rf'\b{re.escape(city)}\b', loc_lower) for city in _INDIA_CITY_TERMS):
            return False

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
    'head of',
    'head ',
    'global head',
    'vp ',
    'vp,',
    'svp ',
    'svp,',
    'evp ',
    'evp,',
    'vice president',
    'senior vice president',
    'executive vice president',
    'director',
    'chief',
    'principal',
    'managing director',
    'general manager',
    'gm ',
    'gm,',
]
_SENIOR_TITLE_OVERRIDES = [
    'senior client partner',
    'strategic client partner',
    'enterprise client partner',
    'industry client partner',
]
_DEFAULT_TARGET = [

    # Core Customer Success / Experience
    'customer success',
    'client success',
    'customer experience',
    'client experience',
    'customer strategy',
    'customer growth',
    'customer operations',
    'customer transformation',
    'customer excellence',
    'customer engagement',
    'customer lifecycle',
    'customer outcomes',
    'customer value',
    'value realization',
    'customer adoption',

    # Customer Health / Risk / Intelligence
    'customer health',
    'account health',
    'customer intelligence',
    'customer insights',
    'critical accounts',
    'critical customers',
    'customer risk',
    'customer retention',
    'retention strategy',

    # Strategic Accounts / Account Management
    'strategic accounts',
    'strategic account',
    'enterprise accounts',
    'enterprise account management',
    'global accounts',
    'global account management',
    'key accounts',
    'major accounts',
    'account management',
    'strategic customers',

    # Renewals / Post-Sales
    'renewals',
    'renewal strategy',
    'post-sales',
    'post sales',
    'customer success & services',
    'customer success and services',
    'success & services',
    'success and services',

    # Client Partner / Strategic IC
    'client partner',
    'strategic client partner',
    'enterprise client partner',
    'industry client partner',

    # Services / Delivery
    'professional services',
    'customer delivery',
    'client delivery',
    'service delivery',

    # AI / Transformation
    'ai transformation',
    'ai adoption',
    'enterprise ai transformation',
    'digital transformation',
    'enterprise transformation',

    # Partnerships / Ecosystem
    'strategic partnerships',
    'partnerships',
    'alliances',
    'ecosystem',
    'channel strategy',

    # Selected Strategic Leadership
    'strategic programs',
    'strategic initiatives',
    'chief of staff',
    'general manager',

    # Chief Customer roles
    'chief customer officer',
    'chief experience officer',
]
_DEFAULT_EXCLUDE = [

    # Engineering / technical individual-contributor functions
    'software engineer',
    'security engineer',
    'data engineer',
    'machine learning engineer',
    'ml engineer',
    'devops',
    'backend',
    'frontend',
    'fullstack',
    'full-stack',
    'site reliability',
    'sre ',
    'qa ',
    'quality assurance',
    'data science',
    'scientist',
    'researcher',

    # Technical pre-sales
    'sales engineer',
    'solutions engineer',
    'solution engineer',
    'solutions engineering',
    'pre-sales',
    'presales',

    # Direct hunter sales
    'account executive',
    'sales director',
    'director of sales',
    'regional sales',
    'area sales',
    'field sales',
    'inside sales',
    'sales development',
    'business development representative',
    'sales development representative',

    # Marketing
    'marketing operations',
    'marketing ops',
    'growth marketing',
    'product marketing',
    'demand generation',
    'brand ',
    'content director',
    'creative director',
    'communications',
    'public relations',

    # HR / Recruiting
    'recruiter',
    'recruiting',
    'talent acquisition',
    'human resources',
    'people operations',
    'compensation',
    'benefits',

    # Legal
    'general counsel',
    'legal counsel',
    'attorney',

    # Finance / Accounting FUNCTIONS
    'director of finance',
    'finance director',
    'financial planning',
    'fp&a',
    'accounting director',
    'director of accounting',
    'controller',
    'controllership',
    'treasury',
    'tax ',

    # Pure RevOps / Sales Ops
    'director of revenue operations',
    'director revenue operations',
    'vp revenue operations',
    'vice president revenue operations',
    'head of revenue operations',
    'director of sales operations',
    'director sales operations',
    'vp sales operations',
    'head of sales operations',

    # Clearly unrelated functions
    'procurement',
    'supply chain',
    'logistics',
    'facilities',
    'real estate',
    'clinical',
    'medical',
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


def is_too_old(job: dict, days: int = 60) -> bool:
    date_str = (job.get('date_posted') or '')[:10]
    if not date_str:
        return False
    try:
        return datetime.strptime(date_str, '%Y-%m-%d') < datetime.utcnow() - timedelta(days=days)
    except ValueError:
        return False



def passes_title_filter(job: dict, profile: dict = None) -> bool:
    profile = profile or {}
    location, seniority, target, exclude = _build_filter_lists(profile)

    title = (job.get('job_title') or '').lower()
    loc = (job.get('location_raw') or '').strip()

    if not _location_ok(loc, location):
        return False

    has_seniority = (
        any(s in title for s in seniority)
        or any(s in title for s in _SENIOR_TITLE_OVERRIDES)
    )

    has_exclude = any(s in title for s in exclude)
    has_target = any(f in title for f in target)

    return has_seniority and not has_exclude and has_target
