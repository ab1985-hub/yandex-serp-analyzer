"""
Yandex SERP Parser

Takes raw HTML from a Yandex search page and extracts:
  - organic results (title, description, url, domain, position)
  - ad results      (title, description, url, domain, position)

Strategy (layered fallbacks):
  A. Direct class selectors (.organic, .adv-block, .direct-item)
  B. Container-level scan (li.serp-item) + "Реклама" badge check
  C. Any heading+link heuristic as last resort

Returns ParseResult with:
  - organic: list of normalised dicts
  - ads:     list of normalised dicts
  - debug:   selector stats, selectors_used, fragment sample
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result structures
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    organic: list[dict] = field(default_factory=list)
    ads: list[dict] = field(default_factory=list)
    debug: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Selector constants
# ---------------------------------------------------------------------------

# Organic selectors — tried in order, first match wins for container detection
_ORGANIC_CONTAINER_SELECTORS = [
    "div.organic",
    "div[class*='organic_']",
    "li[class*='serp-item']:not([class*='adv'])",
    "li[data-cid]",
]

# Ad container selectors
_AD_CONTAINER_SELECTORS = [
    "div.adv-block",
    "div[class*='adv-block']",
    "div.direct-item",
    "div[class*='direct-item']",
    "li[class*='serp-item'][class*='adv']",
    "li[class*='serp-item'][class*='paid']",
]

# Title selectors (inside a result container)
_TITLE_SELECTORS = [
    "h2 a",
    "a[class*='title']",
    "a[class*='Title']",
    "h3 a",
    "a[class*='link'][href]",
]

# Description selectors
_DESC_SELECTORS = [
    "[class*='organic__text']",
    "[class*='text-container']",
    "[class*='passage']",
    "[class*='snippet']",
    "[class*='description']",
    "span[class*='text']",
    "p",
]

# URL/domain selectors (for display URL, not href)
_DOMAIN_SELECTORS = [
    "cite",
    "[class*='organic__url']",
    "[class*='organic__subtitle']",
    "[class*='path']",
    "[class*='greenurl']",
]

# Text that marks an ad block
_AD_TEXT_SIGNALS = re.compile(r"\bреклама\b", re.IGNORECASE)
_AD_CLASS_SIGNALS = re.compile(r"adv|direct|paid", re.IGNORECASE)

# Minimum title length to consider a result valid
_MIN_TITLE_LEN = 3


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def parse_serp(html: str, keyword: str = "", debug: bool = True) -> ParseResult:
    soup = BeautifulSoup(html, "lxml")

    # Remove script/style/noscript noise
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    organic: list[dict] = []
    ads: list[dict] = []
    debug_info: dict = {
        "strategy": None,
        "organic_found": 0,
        "ads_found": 0,
        "selectors_tried": [],
        "html_snippet": html[:800].replace("\n", " "),
    }

    # -----------------------------------------------------------------------
    # Strategy A: direct .organic div scanning
    # -----------------------------------------------------------------------
    organic_divs = _select_first(soup, _ORGANIC_CONTAINER_SELECTORS, debug_info, "organic_containers")
    if organic_divs:
        for i, container in enumerate(organic_divs[:15]):
            r = _extract_result(container, i + 1)
            if r:
                organic.append(r)
        debug_info["strategy"] = "A:organic_divs"

    # Strategy A for ads
    ad_containers = _select_first(soup, _AD_CONTAINER_SELECTORS, debug_info, "ad_containers")
    if ad_containers:
        for i, container in enumerate(ad_containers[:5]):
            r = _extract_result(container, i + 1)
            if r:
                ads.append(r)
        if debug_info.get("strategy"):
            debug_info["strategy"] += "+ad_divs"

    # -----------------------------------------------------------------------
    # Strategy B: scan all serp-item containers, classify by Реклама badge
    # -----------------------------------------------------------------------
    if not organic:
        logger.debug("[PARSER] Strategy A found nothing, trying B (serp-item scan)")
        debug_info["strategy"] = "B:serp_item_scan"
        items = soup.select("li.serp-item, li[data-cid], div[data-cid]")
        debug_info["serp_items_found"] = len(items)

        pos_organic = 1
        pos_ads = 1
        for item in items[:20]:
            is_ad = _item_is_ad(item)
            r = _extract_result(item, pos_ads if is_ad else pos_organic)
            if r:
                if is_ad:
                    ads.append(r)
                    pos_ads += 1
                else:
                    organic.append(r)
                    pos_organic += 1

    # -----------------------------------------------------------------------
    # Strategy C: heuristic link+heading scan
    # -----------------------------------------------------------------------
    if not organic:
        logger.debug("[PARSER] Strategy B found nothing, trying C (heading heuristic)")
        debug_info["strategy"] = "C:heading_heuristic"
        organic = _heuristic_scan(soup)

    # Assign sequential positions
    for i, r in enumerate(organic):
        r["position"] = i + 1
    for i, r in enumerate(ads):
        r["position"] = i + 1

    debug_info["organic_found"] = len(organic)
    debug_info["ads_found"] = len(ads)

    logger.info(
        "[PARSER] '%s' → органика=%d, реклама=%d, стратегия=%s",
        keyword, len(organic), len(ads), debug_info.get("strategy"),
    )

    return ParseResult(organic=organic, ads=ads, debug=debug_info)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _select_first(
    soup: BeautifulSoup,
    selectors: list[str],
    debug_info: dict,
    label: str,
) -> list[Tag]:
    tried = []
    for sel in selectors:
        tried.append(sel)
        found = soup.select(sel)
        if found:
            debug_info[f"{label}_selector"] = sel
            debug_info[f"{label}_count"] = len(found)
            debug_info.setdefault("selectors_tried", []).append(f"{label}:{sel}={len(found)}")
            return found
    debug_info.setdefault("selectors_tried", []).append(f"{label}:none_matched")
    return []


def _item_is_ad(item: Tag) -> bool:
    """Heuristic: is this serp-item an advertisement?"""
    # Check class list
    classes_str = " ".join(item.get("class") or [])
    if _AD_CLASS_SIGNALS.search(classes_str):
        return True
    # Check for "Реклама" text badge anywhere inside
    text = item.get_text(" ")
    if _AD_TEXT_SIGNALS.search(text[:300]):
        return True
    # Check data attributes
    for attr_val in item.attrs.values():
        if isinstance(attr_val, str) and _AD_CLASS_SIGNALS.search(attr_val):
            return True
    return False


def _extract_result(container: Tag, default_pos: int) -> dict | None:
    """Extract a normalised result dict from a container Tag."""
    # -- Title + URL --
    title, url = "", ""
    for sel in _TITLE_SELECTORS:
        el = container.select_one(sel)
        if el:
            candidate_title = el.get_text(strip=True)
            candidate_url = el.get("href", "")
            if len(candidate_title) >= _MIN_TITLE_LEN:
                title = candidate_title
                url = _clean_url(candidate_url)
                break

    if not title:
        return None

    # -- Description --
    description = ""
    for sel in _DESC_SELECTORS:
        el = container.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 20:
                description = text[:500]
                break

    # -- Domain (display URL from <cite> or derive from href) --
    domain = ""
    for sel in _DOMAIN_SELECTORS:
        el = container.select_one(sel)
        if el:
            domain = el.get_text(strip=True).split("/")[0].strip().lower()
            domain = domain.lstrip("www.")
            if domain:
                break

    if not domain and url:
        parsed = urlparse(url)
        domain = parsed.netloc.lstrip("www.")

    return {
        "position": default_pos,
        "title": title,
        "description": description,
        "url": url,
        "domain": domain,
    }


def _heuristic_scan(soup: BeautifulSoup) -> list[dict]:
    """
    Last-resort: find any <h2><a> or <h3><a> pairs that look like results.
    Skips navigation, header, footer.
    """
    results = []
    main = soup.select_one("#search-result, #main, main, #search, div[role='main']") or soup.body
    if not main:
        return results

    for i, heading in enumerate(main.find_all(["h2", "h3"], limit=20)):
        a = heading.find("a", href=True)
        if not a:
            continue
        title = heading.get_text(strip=True)
        if len(title) < 5:
            continue
        url = _clean_url(a.get("href", ""))
        if not url or url.startswith("#"):
            continue
        desc_el = heading.find_next_sibling("p") or heading.find_next("p")
        description = desc_el.get_text(" ", strip=True)[:300] if desc_el else ""
        parsed = urlparse(url)
        domain = parsed.netloc.lstrip("www.")
        results.append({
            "position": i + 1,
            "title": title,
            "description": description,
            "url": url,
            "domain": domain,
        })
    return results


def _clean_url(url: str) -> str:
    """Resolve Yandex redirect URLs (//yandex.ru/clck/...) to the real target."""
    if not url:
        return ""
    # Yandex uses // protocol-relative
    if url.startswith("//"):
        url = "https:" + url
    # Keep absolute URLs as-is, skip relative and js: anchors
    if url.startswith("http"):
        return url
    return ""
