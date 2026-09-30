from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Tuple


# =============================================================================
# LOCATION DATA
# =============================================================================

_US_STATES_FULL = [
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
]

_US_STATES_ABBR = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC',
]

_NON_US_COUNTRY_TERMS = [
    'canada',
    'mexico',
    'india',

    'united kingdom',
    'england',
    'scotland',
    'wales',
    'northern ireland',

    'australia',
    'new zealand',

    'singapore',
    'germany',
    'france',
    'ireland',
    'philippines',
    'brazil',
    'japan',
    'china',
    'poland',
    'spain',
    'netherlands',
    'switzerland',
    'sweden',
    'norway',
    'denmark',
    'finland',
    'italy',
    'portugal',
    'israel',
    'south korea',
    'korea',
]

_NON_US_REGION_TERMS = [
    'emea',
    'apac',
    'asia pacific',
    'europe only',
    'european union',
    'latin america',
    'latam',
]


# Some ATS systems use "IN" for India, which conflicts with Indiana.
_INDIA_CITY_TERMS = [
    'bangalore',
    'bengaluru',
    'mumbai',
    'new delhi',
    'delhi',
    'hyderabad',
    'pune',
    'chennai',
    'gurgaon',
    'gurugram',
    'noida',
    'kolkata',
    'ahmedabad',
    'jaipur',
    'kochi',
    'coimbatore',
    'chandigarh',
    'mysore',
    'mysuru',
    'trivandrum',
    'thiruvananthapuram',
    'vadodara',
    'nagpur',
]


# =============================================================================
# FALLBACK PROFILE VALUES
#
# These are used ONLY if the corresponding profile field is blank.
#
# Your actual profile values should normally take precedence.
# =============================================================================

_DEFAULT_SENIORITY = [
    'vp',
    'vice president',
    'head of',
    'head',
    'chief customer officer',
    'chief experience officer',
    'svp',
    'senior vice president',
    'global head',
    'director',
    'managing director',
    'executive director',
    'principal',
    'practice leader',
    'business unit leader',
    'general manager',
    'managing partner',
    'client executive',
    'regional vice president',
    'global director',
]


_DEFAULT_TARGET = [
    # Customer success / experience
    'customer success',
    'client success',
    'client adoption',
    'client engagement',
    'customer solutions',
    'business value',
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
    'customer health',
    'account health',
    'customer intelligence',
    'customer insights',
    'critical accounts',
    'critical customers',
    'customer risk',
    'customer retention',
    'retention strategy',

    # Strategic accounts / AM
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

    # Renewals / post-sales
    'renewals',
    'renewal strategy',
    'post-sales',
    'post sales',
    'customer success & services',
    'customer success and services',
    'success & services',
    'success and services',

    # Strategic IC
    'client partner',
    'strategic client partner',
    'enterprise client partner',
    'industry client partner',

    # Services
    'professional services',
    'customer delivery',
    'client delivery',
    'service delivery',

    # AI / transformation
    'ai transformation',
    'ai adoption',
    'enterprise ai transformation',
    'digital transformation',
    'enterprise transformation',

    # Partnerships
    'strategic partnerships',
    'partnerships',
    'alliances',
    'ecosystem',
    'channel strategy',

    # Programs / other leadership
    'strategic programs',
    'strategic initiatives',
    'chief of staff',
    'general manager',
    'chief customer officer',
    'chief experience officer',
]


_DEFAULT_EXCLUDE = [
    # Engineering / technical IC
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
    'sre',
    'qa',
    'quality assurance',
    'data science',
    'scientist',
    'researcher',
    'developer',

    # Pre-sales / technical sales
    'sales engineer',
    'solutions engineer',
    'solution engineer',
    'solutions engineering',
    'pre-sales',
    'presales',

    # New-logo sales
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
    'brand',
    'content director',
    'creative director',
    'communications',
    'public relations',

    # Product
    'product manager',
    'product management',

    # HR
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

    # Finance functional roles
    'director of finance',
    'finance director',
    'financial planning',
    'fp&a',
    'accounting director',
    'director of accounting',
    'controller',
    'controllership',
    'treasury',
    'tax',

    # RevOps / Sales Ops
    'director of revenue operations',
    'director revenue operations',
    'vp revenue operations',
    'vice president revenue operations',
    'head of revenue operations',

    'director of sales operations',
    'director sales operations',
    'vp sales operations',
    'head of sales operations',

    # Other
    'procurement',
    'supply chain',
    'logistics',
    'facilities',
    'real estate',
    'clinical',
    'medical',

    # Support / call center
    'customer support',
    'technical support',
    'help desk',
    'call center',
]


# =============================================================================
# SAFE ADDITIONAL TITLE ALIASES
#
# These supplement the profile rather than replace it.
#
# They address title variants that have appeared in the actual job search
# but are easy to miss with literal profile matching.
# =============================================================================

_ADDITIONAL_TARGET_ALIASES = [
    'global client partner',
    'executive client partner',
    'customer partner',

    'strategic account management',

    'enterprise am',
    'strategic am',
    'global am',

    'customer success leader',
    'customer experience leader',
    'cs leader',

    'customer transformation',
    'technology transformation',

    'partner success',
    'partner experience',

    'value consulting',
    'strategy consulting',
]


# These titles are intentionally allowed to satisfy the seniority requirement
# even if they don't contain Director / VP / Head / Principal.
#
# This preserves the senior strategic IC lane.
_SENIOR_IC_PATTERNS = [
    r'\bstrategic client partner\b',
    r'\benterprise client partner\b',
    r'\bindustry client partner\b',
    r'\bglobal client partner\b',
    r'\bexecutive client partner\b',
    r'\bclient partner\b',

    r'\bclient executive\b',

    r'\bexecutive customer success leader\b',
    r'\bcustomer success leader\b',
    r'\bcustomer experience leader\b',
    r'\bexecutive cs leader\b',

    r'\bstrategic accounts lead\b',
    r'\baccount management lead\b',

    r'\benterprise am lead\b',
    r'\bstrategic am lead\b',
    r'\bglobal am lead\b',

    r'\bai transformation lead\b',
    r'\bcustomer transformation lead\b',

    r'\bpractice leader\b',
    r'\bbusiness unit leader\b',
]


# Strongest functional signals for ranking.
#
# These are bonuses only. They are NOT required to pass.
_HIGH_PRIORITY_TARGETS = [
    'customer success',
    'client success',

    'strategic accounts',
    'strategic account',

    'enterprise account management',
    'global account management',
    'account management',

    'customer growth',
    'customer retention',
    'renewals',
    'post-sales',
    'post sales',

    'customer outcomes',
    'customer value',
    'value realization',
    'customer adoption',

    'client partner',
    'strategic client partner',
    'enterprise client partner',
    'global client partner',
    'executive client partner',

    'ai transformation',
    'ai adoption',
    'enterprise ai transformation',

    'professional services',
]


# =============================================================================
# TEXT HELPERS
# =============================================================================

def _normalize_text(value: Any) -> str:
    """
    Normalize text for reliable title matching.

    Examples:
        "Customer Success & Services"
        -> "customer success and services"

        "VP, Strategic-Accounts"
        -> "vp strategic accounts"
    """

    value = str(value or '').lower()

    value = value.replace('&', ' and ')

    value = re.sub(
        r'[-_/|,;:()\[\]{}]+',
        ' ',
        value
    )

    value = re.sub(
        r'\s+',
        ' ',
        value
    )

    return value.strip()


def _parse_list(value: Any) -> List[str]:
    """
    Parse profile fields supplied as:

        comma-separated text
        pipe-separated text
        Python list
        Python tuple
        Python set

    Commas and pipes can safely coexist.
    """

    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        ]

    text = str(value).strip()

    if not text:
        return []

    return [
        item.strip().lower()
        for item in re.split(r'[|,]', text)
        if item.strip()
    ]


def _profile_get(
    profile: Dict[str, Any],
    *keys: str,
    default: Any = None
) -> Any:
    """
    Read a profile value while tolerating common key naming variations.
    """

    profile = profile or {}

    for key in keys:
        if key in profile:
            value = profile.get(key)

            if value is not None and str(value).strip() != '':
                return value

    return default


def _contains_phrase(
    normalized_text: str,
    phrase: str
) -> bool:
    """
    Match phrases on word boundaries rather than using loose substring logic.

    This prevents mistakes such as:
        "market" matching "marketing"
        "tax" matching "syntax"
        "brand" matching unrelated longer words
    """

    phrase_norm = _normalize_text(phrase)

    if not phrase_norm:
        return False

    return bool(
        re.search(
            rf'(?<!\w){re.escape(phrase_norm)}(?!\w)',
            normalized_text
        )
    )


def _phrase_matches(
    normalized_text: str,
    phrases: List[str]
) -> List[str]:

    matches = []

    for phrase in phrases:
        if _contains_phrase(
            normalized_text,
            phrase
        ):
            matches.append(phrase)

    return matches


# =============================================================================
# LOCATION HELPERS
# =============================================================================

def _has_us_signal(loc: str) -> bool:
    raw = (loc or '').strip()
    lower = raw.lower()

    if not raw:
        return False

    # Full country name.
    if re.search(
        r'\bunited\s+states\b',
        lower
    ):
        return True

    # US / USA / U.S. / U.S.A.
    if re.search(
        r'(?<![A-Za-z])(?:US|USA|U\.S\.|U\.S\.A\.)(?![A-Za-z])',
        raw
    ):
        return True

    # Full state names.
    for state in _US_STATES_FULL:
        if re.search(
            rf'\b{re.escape(state)}\b',
            lower
        ):
            return True

    india_city_present = any(
        re.search(
            rf'\b{re.escape(city)}\b',
            lower
        )
        for city in _INDIA_CITY_TERMS
    )

    canada_present = bool(
        re.search(
            r'\bcanada\b',
            lower
        )
    )

    # State abbreviations.
    #
    # Require ATS-style uppercase codes to avoid:
    #   IN = ordinary "in"
    #   OR = ordinary "or"
    #   ME = ordinary "me"
    #
    for abbr in _US_STATES_ABBR:

        if abbr == 'IN' and india_city_present:
            continue

        if abbr == 'CA' and canada_present:
            continue

        if re.search(
            rf'(?<![A-Za-z]){abbr}(?![A-Za-z])',
            raw
        ):
            return True

    # A bare state abbreviation such as "co".
    if lower in {
        abbr.lower()
        for abbr in _US_STATES_ABBR
    }:
        return True

    return False


def _has_non_us_signal(loc: str) -> bool:
    raw = (loc or '').strip()
    lower = raw.lower()

    if not raw:
        return False

    for term in _NON_US_COUNTRY_TERMS:
        if re.search(
            rf'\b{re.escape(term)}\b',
            lower
        ):
            return True

    for term in _NON_US_REGION_TERMS:
        if re.search(
            rf'\b{re.escape(term)}\b',
            lower
        ):
            return True

    for city in _INDIA_CITY_TERMS:
        if re.search(
            rf'\b{re.escape(city)}\b',
            lower
        ):
            return True

    # UK / GB codes.
    if re.search(
        r'(?<![A-Za-z])(?:UK|GB)(?![A-Za-z])',
        raw
    ):
        return True

    return False


def _location_ok(
    loc: str,
    mode: str
) -> bool:
    """
    Supported modes:

        us only
        us eligible
        remote only
        any

    Philosophy:
        Keep potentially workable US roles visible.
        Do not require Colorado / Remote specifically.
        Location flexibility can be assessed downstream.

    Important behavior:

        "United States | Canada | UK"
            -> passes US-only

        "Remote - United States"
            -> passes

        "Remote"
            -> passes

        "Remote - India"
            -> fails

        "Bangalore, IN"
            -> fails

        "Indianapolis, IN"
            -> passes

        "North America"
            -> passes
    """

    if not loc:
        # Fail open on missing ATS location data.
        return True

    raw = loc.strip()
    lower = raw.lower()

    mode = (
        mode or 'us only'
    ).strip().lower()

    if mode in {
        'any',
        'all',
        'no filter',
    }:
        return True

    has_us = _has_us_signal(raw)
    has_non_us = _has_non_us_signal(raw)

    is_remote = bool(
        re.search(
            r'\bremote\b',
            lower
        )
    )

    north_america = bool(
        re.search(
            r'\bnorth america\b',
            lower
        )
    )

    # ---------------------------------------------------------------------
    # Remote-only
    # ---------------------------------------------------------------------

    if mode in {
        'remote',
        'remote only',
    }:

        if not is_remote:
            return False

        if has_us:
            return True

        if north_america:
            return True

        if has_non_us:
            return False

        # Bare "Remote" is ambiguous but potentially valid.
        return True

    # ---------------------------------------------------------------------
    # US-only / US-eligible
    # ---------------------------------------------------------------------

    if mode in {
        'us',
        'us only',
        'united states',
        'us eligible',
    }:

        # Explicit US availability wins even when other countries
        # are also listed.
        if has_us:
            return True

        if north_america:
            return True

        if has_non_us:
            return False

        if lower == 'remote':
            return True

        return False

    # Unknown mode: fail open rather than hide jobs unexpectedly.
    return True


# =============================================================================
# PROFILE FILTER LISTS
# =============================================================================

def _build_filter_lists(
    profile: Dict[str, Any]
) -> Tuple[str, List[str], List[str], List[str]]:
    """
    Return:

        location
        seniority keywords
        target functions
        exclude functions

    Profile values always take precedence over defaults.
    """

    profile = profile or {}

    location = str(
        _profile_get(
            profile,
            'location',
            'Location',
            default='us only'
        )
    ).strip().lower()

    seniority = _parse_list(
        _profile_get(
            profile,
            'seniority_keywords',
            'Seniority Keywords',
            'seniority',
            default=''
        )
    )

    target = _parse_list(
        _profile_get(
            profile,
            'target_functions',
            'Target Functions',
            'target',
            default=''
        )
    )

    exclude = _parse_list(
        _profile_get(
            profile,
            'exclude_functions',
            'Exclude Functions',
            'exclude',
            default=''
        )
    )

    if not seniority:
        seniority = list(_DEFAULT_SENIORITY)

    if not target:
        target = list(_DEFAULT_TARGET)

    if not exclude:
        exclude = list(_DEFAULT_EXCLUDE)

    # Safe aliases supplement rather than replace the profile.
    for alias in _ADDITIONAL_TARGET_ALIASES:
        if alias not in target:
            target.append(alias)

    return (
        location,
        seniority,
        target,
        exclude,
    )


def _get_score_threshold(
    profile: Dict[str, Any]
) -> int:
    """
    Read the profile score threshold.

    Your configured value is currently 6.
    """

    value = _profile_get(
        profile or {},
        'score_threshold',
        'Score Threshold',
        'score threshold',
        default=6
    )

    try:
        return int(value)

    except (TypeError, ValueError):
        return 6


# =============================================================================
# SENIORITY MATCHING
# =============================================================================

def _is_senior_ic_title(
    normalized_title: str
) -> bool:

    return any(
        re.search(
            pattern,
            normalized_title
        )
        for pattern in _SENIOR_IC_PATTERNS
    )


def _executive_level_bonus(
    normalized_title: str
) -> int:
    """
    Small ranking bonus for clear VP/Head/Chief/GM-level titles.

    This does NOT determine pass/fail by itself.
    """

    executive_patterns = [
        r'\bchief\b',
        r'\bevp\b',
        r'\bsvp\b',
        r'\bsenior vice president\b',
        r'\bavp\b',
        r'\bvice president\b',
        r'\bvp\b',
        r'\bhead of\b',
        r'\bglobal head\b',
        r'\bmanaging director\b',
        r'\bgeneral manager\b',
        r'\bmanaging partner\b',
    ]

    if any(
        re.search(
            pattern,
            normalized_title
        )
        for pattern in executive_patterns
    ):
        return 1

    return 0


# =============================================================================
# TITLE SCORING
# =============================================================================

def score_title_fit(
    job: Dict[str, Any],
    profile: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Score and explain title fit.

    IMPORTANT:

    A role must normally satisfy BOTH:

        1. Seniority
        2. Target function

    before it can pass.

    This fixes the issue where a score threshold of 6 could otherwise allow
    a junior "Customer Success Manager" simply because the functional phrase
    itself scored highly.

    Base score:

        seniority match        +3
        target-function match  +3

    Therefore a normal valid role reaches the profile threshold of 6.

    Additional points rank stronger roles higher but are not required to pass.
    """

    profile = profile or {}

    title = (
        job.get('job_title')
        or job.get('title')
        or ''
    ).strip()

    loc = (
        job.get('location_raw')
        or job.get('location')
        or ''
    ).strip()

    normalized_title = _normalize_text(title)

    (
        location_mode,
        seniority_terms,
        target_terms,
        exclude_terms,
    ) = _build_filter_lists(profile)

    threshold = _get_score_threshold(profile)

    # ---------------------------------------------------------------------
    # Location
    # ---------------------------------------------------------------------

    location_pass = _location_ok(
        loc,
        location_mode
    )

    # ---------------------------------------------------------------------
    # Empty title
    # ---------------------------------------------------------------------

    if not normalized_title:
        return {
            'passes': False,
            'score': 0,
            'threshold': threshold,
            'location_pass': location_pass,
            'seniority_pass': False,
            'target_pass': False,
            'exclude_pass': True,
            'seniority_matches': [],
            'target_matches': [],
            'exclude_matches': [],
            'reasons': ['missing job title'],
        }

    # ---------------------------------------------------------------------
    # Hard exclusions
    # ---------------------------------------------------------------------

    exclude_matches = _phrase_matches(
        normalized_title,
        exclude_terms
    )

    if exclude_matches:
        return {
            'passes': False,
            'score': -100,
            'threshold': threshold,
            'location_pass': location_pass,
            'seniority_pass': False,
            'target_pass': False,
            'exclude_pass': False,
            'seniority_matches': [],
            'target_matches': [],
            'exclude_matches': exclude_matches,
            'reasons': [
                f"excluded title signal: {exclude_matches[0]}"
            ],
        }

    # ---------------------------------------------------------------------
    # Seniority
    # ---------------------------------------------------------------------

    seniority_matches = _phrase_matches(
        normalized_title,
        seniority_terms
    )

    explicit_seniority = bool(
        seniority_matches
    )

    senior_ic = _is_senior_ic_title(
        normalized_title
    )

    seniority_pass = (
        explicit_seniority
        or senior_ic
    )

    # ---------------------------------------------------------------------
    # Target function
    # ---------------------------------------------------------------------

    target_matches = _phrase_matches(
        normalized_title,
        target_terms
    )

    target_pass = bool(
        target_matches
    )

    # ---------------------------------------------------------------------
    # Score
    # ---------------------------------------------------------------------

    score = 0
    reasons = []

    if seniority_pass:
        score += 3

        if explicit_seniority:
            reasons.append(
                f"seniority: {seniority_matches[0]}"
            )

        else:
            reasons.append(
                'seniority: approved senior strategic IC title'
            )

    if target_pass:
        score += 3

        reasons.append(
            f"target function: {target_matches[0]}"
        )

    # Clear executive title.
    exec_bonus = _executive_level_bonus(
        normalized_title
    )

    if exec_bonus:
        score += exec_bonus

        reasons.append(
            'executive-level title'
        )

    # Strongest career-lane matches.
    high_priority_matches = _phrase_matches(
        normalized_title,
        _HIGH_PRIORITY_TARGETS
    )

    if high_priority_matches:
        score += 1

        reasons.append(
            f"high-priority lane: {high_priority_matches[0]}"
        )

    # Multiple distinct relevant signals are meaningful.
    if len(target_matches) >= 2:
        score += 1

        reasons.append(
            'multiple target-function signals'
        )

    # Cap title-fit score at 10 for easier downstream interpretation.
    score = min(
        score,
        10
    )

    # ---------------------------------------------------------------------
    # PASS / FAIL
    # ---------------------------------------------------------------------

    #
    # The gates matter more than raw score:
    #
    #   - senior enough
    #   - relevant function
    #   - right geography
    #   - not explicitly excluded
    #
    # Then threshold is applied.
    #

    passes = (
        location_pass
        and seniority_pass
        and target_pass
        and score >= threshold
    )

    if not location_pass:
        reasons.append(
            'location failed'
        )

    if not seniority_pass:
        reasons.append(
            'no seniority signal'
        )

    if not target_pass:
        reasons.append(
            'no target-function signal'
        )

    if score < threshold:
        reasons.append(
            f"score below threshold ({score} < {threshold})"
        )

    return {
        'passes': passes,
        'score': score,
        'threshold': threshold,

        'location_pass': location_pass,

        'seniority_pass': seniority_pass,
        'target_pass': target_pass,
        'exclude_pass': True,

        'seniority_matches': seniority_matches,
        'target_matches': target_matches,
        'exclude_matches': [],

        'reasons': reasons,
    }


# =============================================================================
# PRIMARY DROP-IN TITLE FILTER
# =============================================================================

def passes_title_filter(
    job: Dict[str, Any],
    profile: Dict[str, Any] = None
) -> bool:
    """
    Drop-in replacement for the original filter.

    A job passes only when it:

        1. passes location rules
        2. is senior enough
        3. contains an approved target-function signal
        4. contains no hard exclusion
        5. reaches the configured score threshold

    This protects against both:

        FALSE POSITIVES
            Customer Success Manager
            VP Sales
            Director Corporate Strategy
            VP Revenue Operations
            Enterprise Account Executive

        FALSE NEGATIVES
            Strategic Client Partner
            Executive Customer Success Leader
            Enterprise AM Lead
            VP Sales - Account Management
            Head of Accounting & Advisory Partnerships
    """

    return score_title_fit(
        job,
        profile
    )['passes']


# =============================================================================
# AGE / FRESHNESS
# =============================================================================

def is_too_old(
    job: Dict[str, Any],
    days: int = 45
) -> bool:
    """
    Executive jobs often remain open longer than standard IC roles.

    Default age cutoff is therefore 45 days rather than 30.

    Missing or malformed dates fail open so a strong role is not silently
    discarded because the ATS supplied poor metadata.
    """

    date_str = (
        job.get('date_posted')
        or job.get('posted_at')
        or ''
    )

    date_str = str(
        date_str
    )[:10]

    if not date_str:
        return False

    try:
        posted_date = datetime.strptime(
            date_str,
            '%Y-%m-%d'
        ).date()

        cutoff_date = (
            datetime.now(timezone.utc)
            - timedelta(days=days)
        ).date()

        return posted_date < cutoff_date

    except (ValueError, TypeError):
        return False
