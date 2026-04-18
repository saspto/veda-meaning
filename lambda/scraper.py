"""
Scrapes reputed Sanskrit/Vedic sites for verse text and meaning.
Sites tried in priority order per text type.
"""
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TIMEOUT = 12
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


def _strip_tags(html):
    return re.sub(r"<[^>]+>", "", html)


# ---------------------------------------------------------------------------
# Reference normalisation
# ---------------------------------------------------------------------------

def _normalize_ref(ref):
    """Return (text_type, book, chapter, verse_or_none).

    text_type values:
      BG   – Bhagavad Gita
      VR   – Valmiki Ramayana
      RV   – Rig Veda
      KYV  – Krishna Yajur Veda (Taittiriya Samhita)
      SYV  – Shukla Yajur Veda  (Vajasaneyi Samhita)
      HYMN – named Vedic hymn/suktam
      MANTRA – short known mantra
    """
    ref = ref.strip()

    # Bhagavad Gita
    m = re.match(r"(?:BG|Gita|Bhagavad\s*Gita)\s+(\d+)\.(\d+)", ref, re.I)
    if m:
        return "BG", m.group(1), m.group(2), None

    # Valmiki Ramayana
    m = re.match(r"(?:VR|Valmiki\s*Ramayana?)\s+(\d+)\.(\d+)\.(\d+)", ref, re.I)
    if m:
        return "VR", m.group(1), m.group(2), m.group(3)

    # Rig Veda
    m = re.match(r"RV\s+(\d+)\.(\d+)\.(\d+)", ref, re.I)
    if m:
        return "RV", m.group(1), m.group(2), m.group(3)

    # Krishna Yajur Veda: KYV/TYV/TS kanda.prapathaka.anuvaka
    m = re.match(r"(?:KYV|TYV|TS|Taittiriya\s*Samhita)\s+(\d+)\.(\d+)\.(\d+)", ref, re.I)
    if m:
        return "KYV", m.group(1), m.group(2), m.group(3)

    # Shukla Yajur Veda: SYV/YV/VS adhyaya.verse
    m = re.match(r"(?:SYV|YV|VS|Vajasaneyi)\s+(\d+)\.(\d+)", ref, re.I)
    if m:
        return "SYV", m.group(1), m.group(2), None

    # Named hymns / suktams
    hymn_key = _match_hymn(ref)
    if hymn_key:
        return "HYMN", hymn_key, None, None

    # Short mantras
    if re.search(r"gayatri", ref, re.I):
        return "MANTRA", "gayatri", None, None
    if re.search(r"mrityu|mrityunjaya", ref, re.I):
        return "MANTRA", "mahamrityunjaya", None, None
    if re.search(r"\bshanti\b|\bshanthi\b", ref, re.I):
        return "MANTRA", "shanti", None, None

    return "UNKNOWN", ref, None, None


def _match_hymn(ref):
    r = ref.lower()
    patterns = [
        (r"sri\s*suktam|shri\s*suktam|lakshmi\s*suktam", "sri_suktam"),
        (r"purusha\s*suktam?|purush\s*sukt", "purusha_suktam"),
        (r"narayana\s*suktam?|narayan\s*sukt", "narayana_suktam"),
        (r"durga\s*suktam?", "durga_suktam"),
        (r"medha\s*suktam?", "medha_suktam"),
        (r"(?:sri\s*)?rudram|namakam|shri\s*rudra", "rudram"),
        (r"chamakam", "chamakam"),
        (r"\barunam?\b|aruna\s*prashnam?|surya\s*namaskar\s*mantra", "arunam"),
        (r"vishnu\s*suktam?", "vishnu_suktam"),
        (r"bhu\s*suktam?|bhumi\s*suktam?", "bhu_suktam"),
        (r"nila\s*suktam?", "nila_suktam"),
        (r"manyu\s*suktam?", "manyu_suktam"),
        (r"pavamana\s*suktam?", "pavamana_suktam"),
        (r"hiranya\s*garbha\s*suktam?", "hiranyagarbha_suktam"),
    ]
    for pattern, key in patterns:
        if re.search(pattern, r):
            return key
    return None


# ---------------------------------------------------------------------------
# Complete known hymn texts (Devanagari)
# ---------------------------------------------------------------------------

KNOWN_MANTRAS = {
    "gayatri": (
        "ॐ भूर्भुवः स्वः ।\n"
        "तत्सवितुर्वरेण्यं भर्गो देवस्य धीमहि ।\n"
        "धियो यो नः प्रचोदयात् ॥"
    ),
    "mahamrityunjaya": (
        "ॐ त्र्यम्बकं यजामहे सुगन्धिं पुष्टिवर्धनम् ।\n"
        "उर्वारुकमिव बन्धनान् मृत्योर्मुक्षीय मामृतात् ॥"
    ),
    "shanti": (
        "ॐ सह नाववतु । सह नौ भुनक्तु । सह वीर्यं करवावहै ।\n"
        "तेजस्विनावधीतमस्तु मा विद्विषावहै ।\n"
        "ॐ शान्तिः शान्तिः शान्तिः ॥"
    ),
}

KNOWN_HYMNS = {
    "sri_suktam": """\
॥ श्रीसूक्तम् ॥

ॐ हिरण्यवर्णां हरिणीं सुवर्णरजतस्रजाम् ।
चन्द्रां हिरण्मयीं लक्ष्मीं जातवेदो म आवह ॥ १॥

तां म आवह जातवेदो लक्ष्मीमनपगामिनीम् ।
यस्यां हिरण्यं विन्देयं गामश्वं पुरुषानहम् ॥ २॥

अश्वपूर्वां रथमध्यां हस्तिनादप्रबोधिनीम् ।
श्रियं देवीमुपह्वये श्रीर्मा देवी जुषताम् ॥ ३॥

कांसोस्मितां हिरण्यप्राकारामार्द्रां ज्वलन्तीं तृप्तां तर्पयन्तीम् ।
पद्मे स्थितां पद्मवर्णां तामिहोपह्वये श्रियम् ॥ ४॥

चन्द्रां प्रभासां यशसा ज्वलन्तीं श्रियं लोके देवजुष्टामुदाराम् ।
तां पद्मिनीमीं शरणमहं प्रपद्येऽलक्ष्मीर्मे नश्यतां त्वां वृणे ॥ ५॥

आदित्यवर्णे तपसोऽधिजातो वनस्पतिस्तव वृक्षोऽथ बिल्वः ।
तस्य फलानि तपसानुदन्तु मायान्तरायाश्च बाह्या अलक्ष्मीः ॥ ६॥

उपैतु मां देवसखः कीर्तिश्च मणिना सह ।
प्रादुर्भूतोऽस्मि राष्ट्रेऽस्मिन् कीर्तिमृद्धिं ददातु मे ॥ ७॥

क्षुत्पिपासामलां ज्येष्ठामलक्ष्मीं नाशयाम्यहम् ।
अभूतिमसमृद्धिं च सर्वां निर्णुद मे गृहात् ॥ ८॥

गन्धद्वारां दुराधर्षां नित्यपुष्टां करीषिणीम् ।
ईश्वरीं सर्वभूतानां तामिहोपह्वये श्रियम् ॥ ९॥

मनसः काममाकूतिं वाचः सत्यमशीमहि ।
पशूनां रूपमन्नस्य मयि श्रीः श्रयतां यशः ॥ १०॥

कर्दमेन प्रजाभूता मयि सम्भव कर्दम ।
श्रियं वासय मे कुले मातरं पद्ममालिनीम् ॥ ११॥

आपः सृजन्तु स्निग्धानि चिक्लीत वस मे गृहे ।
नि च देवीं मातरं श्रियं वासय मे कुले ॥ १२॥

आर्द्रां पुष्करिणीं पुष्टिं पिङ्गलां पद्ममालिनीम् ।
चन्द्रां हिरण्मयीं लक्ष्मीं जातवेदो म आवह ॥ १३॥

आर्द्रां यः करिणीं यष्टिं सुवर्णां हेममालिनीम् ।
सूर्यां हिरण्मयीं लक्ष्मीं जातवेदो म आवह ॥ १४॥

तां म आवह जातवेदो लक्ष्मीमनपगामिनीम् ।
यस्यां हिरण्यं प्रभूतं गावो दास्योऽश्वान् विन्देयं पुरुषानहम् ॥ १५॥

॥ फलश्रुतिः ॥
यः शुचिः प्रयतो भूत्वा जुहुयादाज्यमन्वहम् ।
सूक्तं पञ्चदशर्चं च श्रीकामः सततं जपेत् ॥""",

    "purusha_suktam": """\
॥ पुरुषसूक्तम् ॥
(ऋग्वेद १०.९०, यजुर्वेद ३१)

ॐ सहस्रशीर्षा पुरुषः सहस्राक्षः सहस्रपात् ।
स भूमिं विश्वतो वृत्वाऽत्यतिष्ठद्दशाङ्गुलम् ॥ १॥

पुरुष एवेदं सर्वं यद्भूतं यच्च भव्यम् ।
उतामृतत्वस्येशानो यदन्नेनातिरोहति ॥ २॥

एतावानस्य महिमा अतो ज्यायाँश्च पूरुषः ।
पादोऽस्य विश्वा भूतानि त्रिपादस्यामृतं दिवि ॥ ३॥

त्रिपादूर्ध्व उदैत्पूरुषः पादोऽस्येहाभवत्पुनः ।
ततो विष्वङ् व्यक्रामत् साशनानशने अभि ॥ ४॥

तस्माद्विराळजायत विराजो अधि पूरुषः ।
स जातो अत्यरिच्यत पश्चाद्भूमिमथो पुरः ॥ ५॥

यत्पुरुषेण हविषा देवा यज्ञमतन्वत ।
वसन्तो अस्यासीदाज्यं ग्रीष्म इध्मः शरद्धविः ॥ ६॥

सप्तास्यासन् परिधयस्त्रिः सप्त समिधः कृताः ।
देवा यद्यज्ञं तन्वाना अबध्नन् पुरुषं पशुम् ॥ ७॥

तं यज्ञं बर्हिषि प्रौक्षन् पूरुषं जातमग्रतः ।
तेन देवा अयजन्त साध्या ऋषयश्च ये ॥ ८॥

तस्माद्यज्ञात् सर्वहुतः सम्भृतं पृषदाज्यम् ।
पशूँस्ताँश्चक्रे वायव्यान् आरण्यान् ग्राम्याश्च ये ॥ ९॥

तस्माद्यज्ञात् सर्वहुत ऋचः सामानि जज्ञिरे ।
छन्दाँसि जज्ञिरे तस्माद् यजुस्तस्मादजायत ॥ १०॥

तस्मादश्वा अजायन्त ये के चोभयादतः ।
गावो ह जज्ञिरे तस्मात् तस्माज्जाता अजावयः ॥ ११॥

यत्पुरुषं व्यदधुः कतिधा व्यकल्पयन् ।
मुखं किमस्य कौ बाहू का ऊरू पादा उच्येते ॥ १२॥

ब्राह्मणोऽस्य मुखमासीद् बाहू राजन्यः कृतः ।
ऊरू तदस्य यद्वैश्यः पद्भ्याँ शूद्रो अजायत ॥ १३॥

चन्द्रमा मनसो जातश्चक्षोः सूर्यो अजायत ।
श्रोत्राद्वायुश्च प्राणश्च मुखादग्निरजायत ॥ १४॥

नाभ्या आसीदन्तरिक्षँ शीर्ष्णो द्यौः समवर्तत ।
पद्भ्यां भूमिर्दिशः श्रोत्रात् तथा लोकाँ अकल्पयन् ॥ १५॥

यज्ञेन यज्ञमयजन्त देवास् तानि धर्माणि प्रथमान्यासन् ।
ते ह नाकं महिमानः सचन्त यत्र पूर्वे साध्याः सन्ति देवाः ॥ १६॥""",

    "narayana_suktam": """\
॥ नारायणसूक्तम् ॥
(तैत्तिरीयारण्यक १०.१)

ॐ सहस्रशीर्षं देवं विश्वाक्षं विश्वशम्भुवम् ।
विश्वं नारायणं देवं अक्षरं परमं पदम् ॥ १॥

विश्वतः परमं नित्यं विश्वं नारायणं हरिम् ।
विश्वमेवेदं पुरुषस्तद्विश्वमुपजीवति ॥ २॥

पतिं विश्वस्यात्मेश्वरं शाश्वतं शिवमच्युतम् ।
नारायणं महाज्ञेयं विश्वात्मानं परायणम् ॥ ३॥

नारायणपरो ज्योतिरात्मा नारायणः परः ।
नारायणपरं ब्रह्म तत्त्वं नारायणः परः ॥ ४॥

नारायणपरो ध्याता ध्यानं नारायणः परः ।
यच्च किञ्चित् जगत् सर्वं दृश्यते श्रूयतेऽपि वा ॥ ५॥

अन्तर्बहिश्च तत्सर्वं व्याप्य नारायणः स्थितः ।
अनन्तमव्ययं कविं समुद्रेऽन्तं विश्वशम्भुवम् ॥ ६॥

पद्मकोशप्रतीकाशं हृदयं चाप्यधोमुखम् ।
अधो निष्ट्या वितस्त्यान्ते नाभ्यामुपरि तिष्ठति ॥ ७॥

ज्वालामालाकुलं भाती विश्वस्यायतनं महत् ।
सन्तं तत्र महाज्ञेयं सर्वं तेन विभावयेत् ॥ ८॥

सन्तताभिस्तु शिखाभिः तिभिः ऊर्ध्वमयाभिः ।
नीलतोयदमध्यस्थाद् विद्युल्लेखेव भास्वरा ॥ ९॥

नीवारशूकवत् तन्वी पीता भास्वत्यणूपमा ।
तस्याः शिखाया मध्ये परमात्मा व्यवस्थितः ॥ १०॥

स ब्रह्मा स शिवः स हरिः स इन्द्रः सोऽक्षरः परमः स्वराट् ।
स एव विष्णुः स प्राणः स कालः स अग्निः स चन्द्रमाः ॥ ११॥""",
}


# ---------------------------------------------------------------------------
# Verse scrapers
# ---------------------------------------------------------------------------

def _scrape_vedabase_verse(text_type, book, chapter, verse):
    if text_type != "BG":
        return None
    url = f"https://vedabase.io/en/library/bg/{chapter}/{verse}/"
    html = _get(url)
    for cls in ["r-verse-text", "av-devanagari", "devanagari"]:
        t = _extract(html, "div", **{"class": cls})
        if t:
            return t
    return None


def _scrape_iitk_verse(text_type, book, chapter, verse):
    if text_type != "BG":
        return None
    url = (
        f"https://gitasupersite.iitk.ac.in/srimad"
        f"?language=dv&field_chapter_value={chapter}&field_nsutra_value={verse}&scr=1"
    )
    html = _get(url)
    t = _extract(html, "div", **{"class": "field-item"})
    return t if t else None


def _scrape_valmikiramayan_verse(text_type, book, chapter, verse):
    if text_type != "VR":
        return None
    kanda_map = {
        "1": "bala", "2": "ayodhya", "3": "aranya",
        "4": "kishkindha", "5": "sundara", "6": "yuddha", "7": "uttara",
    }
    kanda = kanda_map.get(book, book)
    url = f"https://www.valmikiramayan.net/{kanda}/sarga{chapter}/sarga{chapter}_dv.htm"
    html = _get(url)
    lines = re.findall(
        r"<p[^>]*class=\"[^\"]*(?:sansk|dev)[^\"]*\"[^>]*>(.*?)</p>", html, re.S | re.I
    )
    if lines:
        clean = [_strip_tags(l).strip() for l in lines]
        return "\n".join(c for c in clean if c)
    return None


def _scrape_sanskritdocs_kyv(text_type, book, chapter, verse):
    """sanskritdocuments.org — Taittiriya Samhita (Krishna Yajur Veda)."""
    if text_type != "KYV":
        return None
    url = "https://sanskritdocuments.org/doc_veda/taittirIyasamhitA.html"
    html = _get(url)
    # Extract <pre> block which holds all the text
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.S | re.I)
    if not pre_match:
        return None
    raw = _strip_tags(pre_match.group(1))

    # Try to find the section matching kanda.prapathaka.anuvaka
    # Verse markers look like ॥ १।१।१॥  (using ।)
    # Or like |1.1.1| in some encodings
    # Build multiple search patterns
    k, p, a = book, chapter, verse
    # Convert Arabic to Devanagari numerals for matching
    dev = {str(i): c for i, c in enumerate("०१२३४५६७८९")}
    k_dev = "".join(dev.get(c, c) for c in k)
    p_dev = "".join(dev.get(c, c) for c in p)
    a_dev = "".join(dev.get(c, c) for c in a)

    patterns = [
        rf"॥\s*{k_dev}[।|\.]\s*{p_dev}[।|\.]\s*{a_dev}\s*॥",
        rf"\|\|\s*{k}\.{p}\.{a}\s*\|\|",
        rf"अनुवाक\s*{a_dev}",
    ]
    for pat in patterns:
        m = re.search(pat, raw)
        if m:
            # Return the surrounding ~1000 chars as context
            start = max(0, m.start() - 50)
            end = min(len(raw), m.end() + 1000)
            return raw[start:end].strip()
    return None


def _scrape_sanskritdocs_syv(text_type, book, chapter, verse):
    """sanskritdocuments.org — Vajasaneyi Samhita (Shukla Yajur Veda)."""
    if text_type != "SYV":
        return None
    url = "https://sanskritdocuments.org/doc_veda/vajasaneyisamhita.html"
    try:
        html = _get(url)
    except Exception:
        # Fallback URL variant
        url = "https://sanskritdocuments.org/doc_veda/vs.html"
        html = _get(url)
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.S | re.I)
    if not pre_match:
        return None
    raw = _strip_tags(pre_match.group(1))

    dev = {str(i): c for i, c in enumerate("०१२३४५६७८९")}
    ch_dev = "".join(dev.get(c, c) for c in chapter)
    v_dev  = "".join(dev.get(c, c) for c in (verse or "1"))

    patterns = [
        rf"॥\s*{ch_dev}[।|\.]\s*{v_dev}\s*॥",
        rf"अध्याय\s*{ch_dev}",
    ]
    for pat in patterns:
        m = re.search(pat, raw)
        if m:
            start = max(0, m.start() - 50)
            end = min(len(raw), m.end() + 1000)
            return raw[start:end].strip()
    return None


def fetch_verse(ref, script):
    text_type, book, chapter, verse = _normalize_ref(ref)

    if text_type == "MANTRA":
        return KNOWN_MANTRAS.get(book)

    if text_type == "HYMN":
        # Return embedded text if we have it; else fall through to Bedrock
        return KNOWN_HYMNS.get(book)

    scrapers = [
        _scrape_vedabase_verse,
        _scrape_iitk_verse,
        _scrape_valmikiramayan_verse,
        _scrape_sanskritdocs_kyv,
        _scrape_sanskritdocs_syv,
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
    if text_type != "BG":
        return None
    url = f"https://vedabase.io/en/library/bg/{chapter}/{verse}/"
    html = _get(url)

    word_for_word = _extract(html, "div", **{"class": "r-synonyms"})
    translation = _extract(html, "div", **{"class": "r-translation"})

    if not word_for_word and not translation:
        return None

    result = {"word_for_word": [], "sentence": [], "source": "vedabase.io"}

    if word_for_word:
        pairs = re.split(r"[;，]", word_for_word)
        for pair in pairs:
            parts = re.split(r"[—–-]", pair, maxsplit=1)
            if len(parts) == 2:
                result["word_for_word"].append({
                    "word": parts[0].strip(),
                    "meaning": parts[1].strip(),
                })

    if translation:
        result["sentence"].append({"text": translation, "lang": "en"})

    return result


def _scrape_wisdomlib_meaning(text_type, book, chapter, verse):
    query = urllib.parse.quote(
        f"Bhagavad Gita {chapter}.{verse}" if text_type == "BG"
        else f"{book} {chapter}.{verse}"
    )
    url = f"https://www.wisdomlib.org/definition/{query}"
    try:
        html = _get(url)
        body = _extract(html, "div", **{"class": "definition-body"})
        if body:
            return {
                "word_for_word": [],
                "sentence": [{"text": body, "lang": "en"}],
                "source": "wisdomlib.org",
            }
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
