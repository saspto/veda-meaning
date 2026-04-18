"""
Scrapes reputed Sanskrit/Vedic sites for verse text and meaning.
Sites tried in priority order per text type.
"""
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", errors="replace")


class _TextExtractor(HTMLParser):
    def __init__(self, tag, attrs_match):
        super().__init__()
        self.tag = tag
        self.attrs_match = attrs_match
        self.found = False
        self.depth = 0
        self.texts = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if not self.found:
            for key, val in self.attrs_match.items():
                if val in (attrs_dict.get(key) or ""):
                    self.found = True
                    self.depth = 1
                    return
        elif self.found:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.found:
            self.depth -= 1
            if self.depth <= 0:
                self.found = False

    def handle_data(self, data):
        if self.found:
            self.texts.append(data)

    def result(self):
        return " ".join(t.strip() for t in self.texts if t.strip())


def _extract(html, tag, **kwargs):
    p = _TextExtractor(tag, kwargs)
    p.feed(html)
    return p.result()


def _normalize_ref(ref):
    """Return (text_type, book, chapter, verse_or_none)."""
    ref = ref.strip()
    # Bhagavad Gita: BG 2.47 or Gita 2.47
    m = re.match(r"(?:BG|Gita|Bhagavad\s*Gita)\s+(\d+)\.(\d+)", ref, re.I)
    if m:
        return "BG", m.group(1), m.group(2), None

    # Ramayana: VR 1.1.1 or Valmiki 1.1.1
    m = re.match(r"(?:VR|Valmiki\s*Ramayana?)\s+(\d+)\.(\d+)\.(\d+)", ref, re.I)
    if m:
        return "VR", m.group(1), m.group(2), m.group(3)

    # Rig Veda: RV 1.1.1
    m = re.match(r"RV\s+(\d+)\.(\d+)\.(\d+)", ref, re.I)
    if m:
        return "RV", m.group(1), m.group(2), m.group(3)

    # Named mantras: Gayatri, Maha Mrityunjaya, Shanti Path
    if re.search(r"gayatri", ref, re.I):
        return "MANTRA", "gayatri", None, None
    if re.search(r"mrityu|mrityunjaya", ref, re.I):
        return "MANTRA", "mahamrityunjaya", None, None
    if re.search(r"shanti|shanthi", ref, re.I):
        return "MANTRA", "shanti", None, None

    return "UNKNOWN", ref, None, None


# ---------------------------------------------------------------------------
# Verse scrapers
# ---------------------------------------------------------------------------

def _scrape_vedabase_verse(text_type, book, chapter, verse):
    """vedabase.io — Bhagavad Gita."""
    if text_type != "BG":
        return None
    url = f"https://vedabase.io/en/library/bg/{chapter}/{verse}/"
    html = _get(url)
    # Sanskrit verse is in .r-verse-text or .av-devanagari
    for cls in ["r-verse-text", "av-devanagari", "devanagari"]:
        t = _extract(html, "div", **{"class": cls})
        if t:
            return t
    return None


def _scrape_iitk_verse(text_type, book, chapter, verse):
    """gitasupersite.iitk.ac.in — Bhagavad Gita."""
    if text_type != "BG":
        return None
    url = f"https://gitasupersite.iitk.ac.in/srimad?language=dv&field_chapter_value={chapter}&field_nsutra_value={verse}&scr=1"
    html = _get(url)
    t = _extract(html, "div", **{"class": "field-item"})
    return t if t else None


def _scrape_valmikiramayan_verse(text_type, book, chapter, verse):
    """valmikiramayan.net — Valmiki Ramayana."""
    if text_type != "VR":
        return None
    kanda_map = {"1": "bala", "2": "ayodhya", "3": "aranya",
                 "4": "kishkindha", "5": "sundara", "6": "yuddha", "7": "uttara"}
    kanda = kanda_map.get(book, book)
    url = f"https://www.valmikiramayan.net/{kanda}/{kanda}sargas.htm"
    # Simplified — direct chapter page
    url = f"https://www.valmikiramayan.net/{kanda}/sarga{chapter}/sarga{chapter}_dv.htm"
    html = _get(url)
    # Extract all Devanagari paragraphs
    lines = re.findall(r"<p[^>]*class=\"[^\"]*(?:sansk|dev)[^\"]*\"[^>]*>(.*?)</p>", html, re.S | re.I)
    if lines:
        clean = [re.sub(r"<[^>]+>", "", l).strip() for l in lines]
        return "\n".join(c for c in clean if c)
    return None


def _scrape_sacred_texts_rv(text_type, book, chapter, verse):
    """sacred-texts.com — Rig Veda."""
    if text_type != "RV":
        return None
    url = f"https://www.sacred-texts.com/hin/rv/rv0{book}0{int(chapter):02d}.htm"
    html = _get(url)
    # sacred-texts uses <p> paragraphs with verse numbers
    blocks = re.findall(r"<p>(.*?)</p>", html, re.S)
    target = f"{chapter}.{verse}"
    for b in blocks:
        if target in b:
            return re.sub(r"<[^>]+>", "", b).strip()
    return None


KNOWN_MANTRAS = {
    "gayatri": (
        "ॐ भूर्भुवः स्वः । तत्सवितुर्वरेण्यं भर्गो देवस्य धीमहि । "
        "धियो यो नः प्रचोदयात् ॥"
    ),
    "mahamrityunjaya": (
        "ॐ त्र्यम्बकं यजामहे सुगन्धिं पुष्टिवर्धनम् । "
        "उर्वारुकमिव बन्धनान् मृत्योर्मुक्षीय मामृतात् ॥"
    ),
    "shanti": (
        "ॐ सह नाववतु । सह नौ भुनक्तु । सह वीर्यं करवावहै । "
        "तेजस्विनावधीतमस्तु मा विद्विषावहै । "
        "ॐ शान्तिः शान्तिः शान्तिः ॥"
    ),
}


def fetch_verse(ref, script):
    text_type, book, chapter, verse = _normalize_ref(ref)

    if text_type == "MANTRA":
        return KNOWN_MANTRAS.get(book)

    scrapers = [
        _scrape_vedabase_verse,
        _scrape_iitk_verse,
        _scrape_valmikiramayan_verse,
        _scrape_sacred_texts_rv,
    ]
    for fn in scrapers:
        try:
            result = fn(text_type, book, chapter, verse)
            if result:
                return result
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Meaning scrapers
# ---------------------------------------------------------------------------

def _scrape_vedabase_meaning(text_type, book, chapter, verse):
    """vedabase.io word-for-word and purport."""
    if text_type != "BG":
        return None
    url = f"https://vedabase.io/en/library/bg/{chapter}/{verse}/"
    html = _get(url)

    word_for_word = _extract(html, "div", **{"class": "r-synonyms"})
    translation = _extract(html, "div", **{"class": "r-translation"})
    purport = _extract(html, "div", **{"class": "r-purport"})

    if not word_for_word and not translation:
        return None

    result = {"word_for_word": [], "sentence": [], "source": "vedabase.io"}

    if word_for_word:
        # Parse "word — meaning; word — meaning" pattern
        pairs = re.split(r"[;，]", word_for_word)
        for pair in pairs:
            parts = re.split(r"[—–-]", pair, maxsplit=1)
            if len(parts) == 2:
                result["word_for_word"].append({
                    "word": parts[0].strip(),
                    "meaning": parts[1].strip()
                })

    if translation:
        result["sentence"].append({"text": translation, "lang": "en"})

    return result


def _scrape_wisdomlib_meaning(text_type, book, chapter, verse):
    """wisdomlib.org — broad coverage."""
    query = urllib.parse.quote(f"Bhagavad Gita {chapter}.{verse}" if text_type == "BG" else f"{book} {chapter}.{verse}")
    url = f"https://www.wisdomlib.org/definition/{query}"
    try:
        html = _get(url)
        body = _extract(html, "div", **{"class": "definition-body"})
        if body:
            return {"word_for_word": [], "sentence": [{"text": body, "lang": "en"}], "source": "wisdomlib.org"}
    except Exception:
        pass
    return None


def fetch_meaning(ref, script):
    text_type, book, chapter, verse = _normalize_ref(ref)
    scrapers = [_scrape_vedabase_meaning, _scrape_wisdomlib_meaning]
    for fn in scrapers:
        try:
            result = fn(text_type, book, chapter, verse)
            if result:
                return result
        except Exception:
            continue
    return None
