from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Location matching
# ---------------------------------------------------------------------------

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
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID',
    'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS',
    'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK',
    'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV',
    'WI', 'WY', 'DC',
]

_NON_US_COUNTRY_TERMS = [
    'canada', 'mexico', 'india', 'united kingdom', 'australia', 'singapore',
    'germany', 'france', 'ireland', 'philippines', 'brazil', 'japan',
    'china', 'poland', 'spain', 'netherlands', 'switzerland', 'sweden',
    'norway', 'denmark', 'finland', 'italy', 'portugal', 'israel',
    'south korea', 'korea', 'new zealand',
]

_NON_US_REGION_TERMS = [
    'emea', 'apac', 'asia pacific', 'europe only', 'european union',
    'latin america', 'latam',
]

# Some ATS systems use "IN" for India, which conflicts with Indiana.
_INDIA_CITY_TERMS = [
    'bangalore', 'bengaluru', 'mumbai', 'new delhi', 'delhi', 'hyderabad',
    'pune', 'chennai', 'gurgaon', 'gurugram', 'noida', 'kolkata',
    'ahmedabad', 'jaipur', 'kochi', 'coimbatore', 'chandigarh', 'mysore',
    'mysuru', 'trivandrum', 'thiruvananthapuram', 'vadodara', 'nagpur',
]


def _normalize_text(value: str) -> str:
    """Normalize text for phrase matching."""
    value = (value or '').lower()
    value = value.replace('&', ' and ')
    value = re.sub(r'[-_/|,;:()\[\]{}]+', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    """
    Match a normalized phrase on word boundaries.

    Avoids accidental matches such as "market" inside "marketing"
    or "cs" inside another word.
    """
    phrase_norm = _normalize_text(phrase)

    if not phrase_norm:
        return False

    return bool(
        re.search(
            rf'(?<!\w){re.escape(phrase_norm)}(?!\w)',
            normalized_text,
        )
    )


def _phrase_matches(normalized_text: str, phrases: List[str]) -> List[str]:
    return [
        phrase
        for phrase in phrases
        if _contains_phrase(normalized_text, phrase)
    ]


def _has_us_signal(loc: str) -> bool:
    raw = (loc or '').strip()
    lower = raw.lower()

    if not raw:
        return False

    if re.search(r'\bunited\s+states\b', lower):
        return True

    # US / USA / U.S. / U.S.A.
    if re.search(
        r'(?<![A-Za-z])(?:US|USA|U\.S\.|U\.S\.A\.)(?![A-Za-z])',
        raw
    ):
        return True

    # Full state names.
    for state in _US_STATES_FULL:
        if re.search(rf'\b{re.escape(state)}\b', lower):
            return True

    india_city_present = any(
        re.search(rf'\b{re.escape(city)}\b', lower)
        for city in _INDIA_CITY_TERMS
    )

    canada_present = bool(re.search(r'\bcanada\b', lower))

    # Prefer uppercase ATS state codes.
    # This avoids IN="in", OR="or", ME="me", etc.
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

    # Allow a field consisting solely of a lowercase state code.
    if lower in {abbr.lower() for abbr in _US_STATES_ABBR}:
        return True

    return False


def _has_non_us_signal(loc: str) -> bool:
    raw = (loc or '').strip()
    lower = raw.lower()

    if not raw:
        return False

    if any(
        re.search(rf'\b{re.escape(term)}\b', lower)
        for term in _NON_US_COUNTRY_TERMS
    ):
        return True

    if any(
        re.search(rf'\b{re.escape(term)}\b', lower)
        for term in _NON_US_REGION_TERMS
    ):
        return True

    if any(
        re.search(rf'\b{re.escape(city)}\b', lower)
        for city in _INDIA_CITY_TERMS
    ):
        return True

    # UK and GB do not conflict with US state abbreviations.
    if re.search(
        r'(?<![A-Za-z])(?:UK|GB)(?![A-Za-z])',
        raw
    ):
        return True

    return False


def _location_ok(loc: str, mode: str) -> bool:
    """
    Location modes:

      "us only"
          US, North America, or ambiguous bare Remote.

      "remote only"
          Must contain Remote and must not clearly be non-US.

      "any"
          No location filtering.

    Explicit US eligibility wins when several countries are listed, e.g.
    "United States | Canada | United Kingdom".
    """

    if not loc:
        return True

    raw = loc.strip()
    lower = raw.lower()

    mode = (mode or 'us only').strip().lower()

    if mode in {'any', 'all', 'no filter'}:
        return True

    has_us = _has_us_signal(raw)
    has_non_us = _has_non_us_signal(raw)

    north_america = bool(
        re.search(r'\bnorth america\b', lower)
    )

    is_remote = 'remote' in lower

    if mode in {'remote', 'remote only'}:

        if not is_remote:
            return False

        if has_us:
            return True

        if north_america:
            return True

        if has_non_us:
            return False

        # Bare/ambiguous Remote: retain rather than silently discard.
        return True

    if mode in {
        'us',
        'us only',
        'united states',
        'us eligible',
    }:

        # Explicit US eligibility wins even if other countries are listed.
        if has_us:
            return True

        # Worth reviewing rather than throwing away.
        if north_america:
            return True

        if has_non_us:
            return False

        if lower == 'remote':
            return True

        return False

    # Unknown mode: fail open rather than unexpectedly hide jobs.
    return True


# ---------------------------------------------------------------------------
# Title matching
# ---------------------------------------------------------------------------

# Core search lane:
#
# Enterprise customer/post-sales leadership
# Strategic accounts / account management
# Customer growth and value
# Strategic client leadership
# AI / enterprise transformation
#
_CORE_TARGETS = [

    # Customer leadership
    'chief customer officer',
    'customer success',
    'client success',
    'customer experience',
    'client experience',
    'customer outcomes',
    'customer growth',
    'customer value',
    'customer strategy',
    'customer transformation',
    'customer adoption',
    'customer engagement',
    'customer health',
    'customer intelligence',
    'customer insights',
    'customer journey',
    'customer excellence',
    'voice of customer',
    'cs leader',

    # Post-sales / lifecycle
    'post sales',
    'post sale',
    'customer lifecycle',
    'success and services',
    'renewals',
    'customer retention',
    'value realization',

    # Account leadership
    'account management',

    'strategic account',
    'strategic accounts',

    'enterprise account',
    'enterprise accounts',

    'global account',
    'global accounts',

    'key account',
    'key accounts',

    'critical account',
    'critical accounts',

    'enterprise am',
    'strategic am',
    'global am',

    # Strategic senior IC
    'client partner',
    'strategic client partner',
    'global client partner',
    'executive client partner',
    'customer partner',

    # AI / transformation
    'ai transformation',
    'ai adoption',
    'enterprise ai',
    'customer ai',
    'digital transformation',
    'enterprise transformation',
    'technology transformation',

    # Deliberate executive path
    'chief of staff',
]


# Strong adjacencies.
#
# These are worth surfacing when title seniority is sufficient.
_STRONG_ADJACENT_TARGETS = [

    # Partnerships / ecosystem
    'strategic partnerships',
    'partnerships',
    'alliances',
    'ecosystem',
    'partner success',
    'partner experience',
    'channel strategy',

    # Services / consulting
    'professional services',
    'client services',
    'strategy consulting',
    'value consulting',

    # Customer-adjacent operating leadership
    'customer operations',
    'customer enablement',

    # Strategic programs
    'strategic programs',

    # GM / business leadership
    'general manager',
    'gm',
    'business unit',
]


# Useful signals, but deliberately too broad to qualify a role by themselves.
_BROAD_ADJACENT_TARGETS = [

    'commercial strategy',
    'commercial operations',

    'business transformation',
    'business planning',

    'strategic planning',
    'corporate strategy',
    'strategic initiatives',

    'transformation office',

    'growth strategy',
    'market expansion',

    'go to market strategy',
    'gtm strategy',

    'pricing strategy',
    'monetization',
    'deal desk',

    'ai strategy',
    'enterprise strategy',
]


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------

# Hard exclusions are intentionally narrow and describe clearly different
# career archetypes.
#
# Important: "financial" and "accounting" are NOT excluded because they often
# describe an industry/vertical rather than the function.
#
_HARD_EXCLUDE = [

    # New-logo / quota IC
    'account executive',
    'sales development representative',
    'business development representative',

    # Technical IC
    'software engineer',
    'backend engineer',
    'frontend engineer',
    'full stack engineer',
    'devops engineer',
    'site reliability engineer',
    'machine learning engineer',
    'data scientist',
    'research scientist',

    # Product career track
    'product manager',
    'product management',
    'product marketing',

    'chief product officer',
    'vp product',
    'vice president product',
    'head of product',
    'director product',
    'director of product',

    # Marketing leadership
    'chief marketing officer',
    'vp marketing',
    'vice president marketing',
    'head of marketing',
    'director marketing',
    'director of marketing',

    # Legal career track
    'general counsel',
    'legal counsel',
    'associate counsel',
    'attorney',

    'chief legal officer',
    'vp legal',
    'vice president legal',
    'head of legal',
    'director legal',
    'director of legal',

    # Finance career track
    'chief financial officer',
    'vp finance',
    'vice president finance',
    'head of finance',
    'director finance',
    'director of finance',
    'controller',
    'controllership',

    # Engineering leadership
    'vp engineering',
    'vice president engineering',
    'head of engineering',
    'director engineering',
    'director of engineering',

    # HR / recruiting
    'recruiter',
    'talent acquisition',
]


# Soft negatives reduce score but do not automatically kill the role.
#
# This lets:
#
#   VP Sales - Account Management
#
# survive, while:
#
#   VP Sales
#
# does not.
#
_SOFT_NEGATIVES = {

    'sales operations': -3,
    'sales ops': -3,

    'revenue operations': -3,
    'revops': -3,
    'rev ops': -3,

    'marketing operations': -4,
    'marketing ops': -4,

    'product operations': -3,
    'product ops': -3,

    'sales enablement': -2,

    'new logo': -4,
    'new business': -2,

    'sales': -2,

    'business development': -1,
}


# ---------------------------------------------------------------------------
# Seniority
# ---------------------------------------------------------------------------

_EXEC_SENIORITY_PATTERNS = [

    r'\bchief\b',

    r'\bevp\b',
    r'\bsvp\b',
    r'\bavp\b',

    r'\bvice president\b',
    r'\bvp\b',

    r'\bhead of\b',

    # Catches titles such as:
    # Global Head, Customer Success
    # Americas Head, Strategic Accounts
    r'\b(?:global |regional |americas |north america )?head\b',

    r'\bmanaging director\b',

    r'\bgeneral manager\b',
    r'\bgm\b',

    r'\bpresident\b',
]


_SENIOR_DIRECTOR_PATTERNS = [
    r'\bsenior director\b',
    r'\bsr director\b',
    r'\bexecutive director\b',
]


_DIRECTOR_PATTERNS = [
    r'\bdirector\b',
]


_PRINCIPAL_PATTERNS = [
    r'\bprincipal\b',
]


# Senior IC titles that may not contain Director / VP / Principal.
_SENIOR_IC_PATTERNS = [

    r'\bexecutive customer success leader\b',
    r'\bcustomer success leader\b',
    r'\bcustomer experience leader\b',
    r'\bexecutive cs leader\b',

    r'\bstrategic accounts lead\b',
    r'\baccount management lead\b',

    r'\benterprise am lead\b',
    r'\bstrategic am lead\b',
    r'\bglobal am lead\b',

    r'\bstrategic client partner\b',
    r'\bglobal client partner\b',
    r'\bexecutive client partner\b',

    r'\bai transformation lead\b',
    r'\bcustomer transformation lead\b',

    r'\bbusiness unit leader\b',
]


# Compatibility aliases in case another module imports the old constants.
_DEFAULT_SENIORITY = [
    'chief',
    'evp',
    'svp',
    'avp',
    'vice president',
    'vp',
    'head',
    'managing director',
    'general manager',
    'gm',
    'senior director',
    'sr director',
    'executive director',
    'director',
    'principal',
]


_DEFAULT_TARGET = (
    _CORE_TARGETS
    + _STRONG_ADJACENT_TARGETS
    + _BROAD_ADJACENT_TARGETS
)


_DEFAULT_EXCLUDE = _HARD_EXCLUDE


# ---------------------------------------------------------------------------
# Profile parsing
# ---------------------------------------------------------------------------

def _parse_list(value: Any) -> List[str]:
    """
    Accept either:

        "foo, bar, baz"

    or:

        "foo|bar|baz"

    or a Python list / tuple / set.
    """

    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        ]

    value = str(value)

    if not value.strip():
        return []

    sep = '|' if '|' in value else ','

    return [
        item.strip().lower()
        for item in value.split(sep)
        if item.strip()
    ]


def _build_filter_lists(
    profile: Dict[str, Any]
) -> Tuple[str, List[str], List[str], List[str]]:
    """
    Compatibility helper retaining the same return shape as the old version:

        location, seniority, target, exclude
    """

    profile = profile or {}

    location = (
        profile.get('location') or ''
    ).strip().lower() or 'us only'

    seniority = (
        _parse_list(profile.get('seniority_keywords'))
        or _DEFAULT_SENIORITY
    )

    target = (
        _parse_list(profile.get('target_functions'))
        or _DEFAULT_TARGET
    )

    exclude = (
        _parse_list(profile.get('exclude_functions'))
        or _DEFAULT_EXCLUDE
    )

    return location, seniority, target, exclude


# ---------------------------------------------------------------------------
# Title scoring
# ---------------------------------------------------------------------------

def _matches_any_regex(
    normalized_title: str,
    patterns: List[str]
) -> bool:

    return any(
        re.search(pattern, normalized_title)
        for pattern in patterns
    )


def _default_seniority_score(
    normalized_title: str
) -> Tuple[int, str]:

    if _matches_any_regex(
        normalized_title,
        _EXEC_SENIORITY_PATTERNS
    ):
        return 4, 'executive seniority'

    if _matches_any_regex(
        normalized_title,
        _SENIOR_DIRECTOR_PATTERNS
    ):
        return 3, 'senior director'

    if _matches_any_regex(
        normalized_title,
        _PRINCIPAL_PATTERNS
    ):
        return 3, 'principal'

    if _matches_any_regex(
        normalized_title,
        _DIRECTOR_PATTERNS
    ):
        return 2, 'director'

    if _matches_any_regex(
        normalized_title,
        _SENIOR_IC_PATTERNS
    ):
        return 4, 'approved senior IC title'

    return 0, ''


def _title_fit_details(
    title: str,
    profile: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Score title fit.

    Default threshold = 7.

    Typical outcomes:

        VP Customer Success
            4 seniority + 6 core = 10
            PASS

        Director Account Management
            2 seniority + 6 core = 8
            PASS

        Strategic Client Partner
            4 senior IC + 6 core = 10
            PASS

        Head of Partnerships
            4 seniority + 5 adjacency = 9
            PASS

        Director Professional Services
            2 seniority + 5 adjacency = 7
            PASS

        VP Corporate Strategy
            4 seniority + 2 broad = 6
            FAIL

        VP Sales
            4 seniority - 2 sales = 2
            FAIL

        VP Sales - Account Management
            4 seniority + 6 core - 2 sales = 8
            PASS
    """

    profile = profile or {}

    normalized_title = _normalize_text(title)

    if not normalized_title:
        return {
            'score': 0,
            'reasons': [],
            'hard_exclude': False,
            'hard_exclude_matches': [],
        }

    custom_seniority = _parse_list(
        profile.get('seniority_keywords')
    )

    custom_target = _parse_list(
        profile.get('target_functions')
    )

    custom_exclude = _parse_list(
        profile.get('exclude_functions')
    )

    # -------------------------------------------------------
    # Hard exclusions
    # -------------------------------------------------------

    excludes = custom_exclude or _HARD_EXCLUDE

    hard_matches = _phrase_matches(
        normalized_title,
        excludes
    )

    if hard_matches:
        return {
            'score': -100,
            'reasons': [],
            'hard_exclude': True,
            'hard_exclude_matches': hard_matches,
        }

    score = 0
    reasons = []

    # -------------------------------------------------------
    # Seniority
    # -------------------------------------------------------

    if custom_seniority:

        seniority_matches = _phrase_matches(
            normalized_title,
            custom_seniority
        )

        if seniority_matches:

            score += 4

            reasons.append(
                f"seniority: {seniority_matches[0]}"
            )

    else:

        seniority_score, seniority_reason = (
            _default_seniority_score(
                normalized_title
            )
        )

        score += seniority_score

        if seniority_reason:
            reasons.append(seniority_reason)

    # -------------------------------------------------------
    # Function
    # -------------------------------------------------------

    if custom_target:

        target_matches = _phrase_matches(
            normalized_title,
            custom_target
        )

        if target_matches:

            score += 6

            reasons.append(
                f"target: {target_matches[0]}"
            )

    else:

        core_matches = _phrase_matches(
            normalized_title,
            _CORE_TARGETS
        )

        strong_matches = _phrase_matches(
            normalized_title,
            _STRONG_ADJACENT_TARGETS
        )

        broad_matches = _phrase_matches(
            normalized_title,
            _BROAD_ADJACENT_TARGETS
        )

        if core_matches:

            score += 6

            reasons.append(
                f"core function: {core_matches[0]}"
            )

        elif strong_matches:

            score += 5

            reasons.append(
                f"strong adjacency: {strong_matches[0]}"
            )

        elif broad_matches:

            score += 2

            reasons.append(
                f"broad adjacency: {broad_matches[0]}"
            )

    # -------------------------------------------------------
    # Soft penalties
    # -------------------------------------------------------

    for phrase, penalty in _SOFT_NEGATIVES.items():

        if _contains_phrase(
            normalized_title,
            phrase
        ):

            score += penalty

            reasons.append(
                f"penalty {penalty}: {phrase}"
            )

    return {
        'score': score,
        'reasons': reasons,
        'hard_exclude': False,
        'hard_exclude_matches': [],
    }


# ---------------------------------------------------------------------------
# Optional diagnostic function
# ---------------------------------------------------------------------------

def score_title_fit(
    job: Dict[str, Any],
    profile: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Optional debugging / ranking helper.

    Existing workflow code does not need to call this.

    Example output:

        {
            "passes": True,
            "score": 10,
            "threshold": 7,
            "location_pass": True,
            "reasons": [
                "executive seniority",
                "core function: account management"
            ],
            "hard_exclude": False,
            "hard_exclude_matches": []
        }
    """

    profile = profile or {}

    title = (
        job.get('job_title') or ''
    ).strip()

    loc = (
        job.get('location_raw') or ''
    ).strip()

    location_mode = (
        profile.get('location') or ''
    ).strip().lower() or 'us only'

    location_pass = _location_ok(
        loc,
        location_mode
    )

    details = _title_fit_details(
        title,
        profile
    )

    try:
        threshold = int(
            profile.get(
                'title_score_threshold',
                7
            )
        )
    except (TypeError, ValueError):
        threshold = 7

    return {

        'passes': (
            location_pass
            and not details['hard_exclude']
            and details['score'] >= threshold
        ),

        'score': details['score'],

        'threshold': threshold,

        'location_pass': location_pass,

        'reasons': details['reasons'],

        'hard_exclude': details['hard_exclude'],

        'hard_exclude_matches':
            details['hard_exclude_matches'],
    }


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------

def is_too_old(
    job: Dict[str, Any],
    days: int = 45
) -> bool:
    """
    Senior roles often remain open longer than 30 days.

    Default cutoff has therefore been moved to 45 days.

    Missing or malformed dates fail open so a potentially good role
    is not silently discarded.
    """

    date_str = (
        job.get('date_posted') or ''
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

    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Primary drop-in filter
# ---------------------------------------------------------------------------

def passes_title_filter(
    job: Dict[str, Any],
    profile: Dict[str, Any] = None
) -> bool:
    """
    Drop-in replacement for the original boolean filter.

    Default priority:

        1. Customer Success / Customer Experience leadership

        2. Strategic / Enterprise Account Management

        3. Customer Growth / Post-Sales / Value Realization

        4. Senior Client Partner / strategic IC roles

        5. AI / Digital / Enterprise Transformation

        6. Partnerships / Alliances

        7. Professional Services / Strategy Consulting

        8. General Manager / Business Unit leadership

        9. Selected Strategic Programs

    Generic words such as:

        strategy
        strategic
        enterprise
        operations
        sales
        revenue
        growth
        market
        commercial

    no longer qualify a job by themselves.
    """

    return score_title_fit(
        job,
        profile
    )['passes']
