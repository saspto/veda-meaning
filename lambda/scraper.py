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

    "arunam": """\
॥ अरुणप्रश्नः ॥
(तैत्तिरीयारण्यकम् — प्रथमप्रश्नः)

॥ प्रथमोऽनुवाकः ॥

ॐ भद्रं कर्णेभिः शृणुयाम देवाः ।
भद्रं पश्येमाक्षभिर्यजत्राः ।
स्थिरैरङ्गैस्तुष्टुवाँसस्तनूभिः ।
व्यशेम देवहितं यदायुः ॥
स्वस्ति न इन्द्रो वृद्धश्रवाः ।
स्वस्ति नः पूषा विश्ववेदाः ।
स्वस्ति नस्तार्क्ष्यो अरिष्टनेमिः ।
स्वस्ति नो बृहस्पतिर्दधातु ।
ॐ शान्तिः शान्तिः शान्तिः ॥

॥ द्वितीयोऽनुवाकः ॥

ॐ आकृष्णेन रजसा वर्तमानो निवेशयन्नमृतं मर्त्यं च ।
हिरण्ययेन सविता रथेना देवो याति भुवनानि पश्यन् ॥
ॐ उद्वयं तमसस्परि स्वः पश्यन्त उत्तरम् ।
देवं देवत्रा सूर्यमगन्म ज्योतिरुत्तमम् ॥
ॐ उदु त्यं जातवेदसं देवं वहन्ति केतवः ।
दृशे विश्वाय सूर्यम् ॥
ॐ चित्रं देवानामुदगादनीकं चक्षुर्मित्रस्य वरुणस्याग्नेः ।
आप्रा द्यावापृथिवी अन्तरिक्षँ सूर्य आत्मा जगतस्तस्थुषश्च ॥
ॐ तच्चक्षुर्देवहितं पुरस्ताच्छुक्रमुच्चरत् ।
पश्येम शरदः शतं जीवेम शरदः शतम् ।
शृणुयाम शरदः शतं प्र ब्रवाम शरदः शतम् ।
अदीनाः स्याम शरदः शतं भूयश्च शरदः शतात् ॥

॥ तृतीयोऽनुवाकः ॥

ॐ नमः सूर्याय नमः सवित्रे नमः सहस्रांशवे ।
नमस्ते अस्तु विवस्वते नमो भास्कराय ।
नमो ब्रह्मणे नमो विष्णवे नमः शिवाय ।
नमः सोमाय नमो वरुणाय नमो यमाय ।
नमो रुद्राय नमो अग्नये नमो वायवे ।
नमः पृथिव्यै नम आकाशाय नमो नभसे ।
नमः सर्वेभ्यो देवेभ्यः ॥

॥ चतुर्थोऽनुवाकः ॥

ॐ सप्त त्वा हरितो रथे वहन्ति देव सूर्य ।
शोचिष्केशं विचक्षण ॥
ॐ आसत्येन रजसा वर्तमानो निवेशयन्नमृतं मर्त्यं च ।
हिरण्ययेन सविता रथेना देवो याति भुवनानि पश्यन् ॥
ॐ हंसः शुचिषद्वसुरन्तरिक्षसद्धोता वेदिषदतिथिर्दुरोणसत् ।
नृषद्वरसदृतसद्व्योमसदब्जा गोजा ऋतजा अद्रिजा ऋतम् ॥

॥ पञ्चमोऽनुवाकः ॥

ॐ उदु त्यं चित्रं देवानां सहस्रांशुं विचक्षणम् ।
रत्नधामन्नित्पातयन्तं दिव्यं सूर्यमदृश्रम् ॥
ॐ तत्सवितुर्वरेण्यं भर्गो देवस्य धीमहि ।
धियो यो नः प्रचोदयात् ॥
ॐ उद्वयं तमसस्परि ज्योतिष्पश्यन्त उत्तरम् ।
देवं देवत्रा सूर्यमगन्म ज्योतिरुत्तमम् ॥

॥ षष्ठोऽनुवाकः ॥

ॐ नमस्ते अरुण रूपाय नमस्ते अस्तु हेतये ।
नमस्ते अस्तु हेत्यै नमस्ते अस्तु धन्वने ॥
ॐ नमो रुद्राय नम उग्राय नमः शर्वाय नमः शिवाय ।
नमस्ते अस्तु रुद्र मन्यव उतो त इषवे नमः ॥
ॐ नमस्ते अस्तु भगवन् विश्वेश्वराय महादेवाय त्र्यम्बकाय ।
त्रिपुरान्तकाय त्रिकालाग्निकालाय कालाग्निरुद्राय ।
नीलकण्ठाय मृत्युञ्जयाय सर्वेश्वराय सदाशिवाय ।
श्रीमन् महादेवाय नमः ॥

॥ सप्तमोऽनुवाकः ॥

ॐ सूर्यो देवः सवितासि देवो ज्योतिर्ज्योतिरसि ।
त्वं सूर्य उदेतासि त्वं सूर्यः शुचिरसि ।
त्वमादित्यो विभ्राजस्व ।
आयुषे त्वा वर्चसे त्वा ।
आयुर्देहि यशो देहि बलं देहि द्विषो जहि ।
प्रीणाहि सवितर्देवं प्रीण शुक्रं बृहस्पतिम् ।
प्रीणीहि वरुणं मित्रमिन्द्रं च सर्वाँश्च देवान् ॥

॥ अष्टमोऽनुवाकः ॥

ॐ ब्रह्म जज्ञानं प्रथमं पुरस्ताद्वि सीमतः सुरुचो वेन आवः ।
स बुध्न्या उपमा अस्य विष्ठाः सतश्च योनिमसतश्च विवः ॥
ॐ ये देवा दिव्येकादश स्थ पृथिव्यामध्येकादश स्थ ।
अप्सुक्षितो महिनैकादश स्थ ते देवासो यज्ञमिमं जुषध्वम् ॥

॥ नवमोऽनुवाकः ॥

ॐ नमो मित्राय नमो अर्यम्णे नमो भगाय नमो वरुणाय ।
नमः सवित्रे नमो भास्कराय नमो विवस्वते नमो आदित्याय ॥
ॐ नमः पूष्णे नमो भगाय नमः प्रजापतये ।
नमस्त्वष्ट्रे नमो वायवे नमः श्येनाय नमः स्कन्दाय ॥
ॐ नमो विष्णवे नमः शिवाय नमो रुद्राय नम उमायै ।
नमः सरस्वत्यै नमो गङ्गायै नमो यमाय ॥

॥ दशमोऽनुवाकः ॥

ॐ एहि सूर्य सहस्रांशो तेजोराशे जगत्पते ।
अनुकम्पय मां भक्त्या गृहाणार्घ्यं दिवाकर ॥
ॐ ध्येयः सदा सवितृमण्डलमध्यवर्ती
नारायणः सरसिजासनसन्निविष्टः ।
केयूरवान् मकरकुण्डलवान् किरीटी
हारी हिरण्मयवपुर्धृतशङ्खचक्रः ॥

॥ एकादशोऽनुवाकः ॥

ॐ आदित्यस्य नमस्कारान् ये कुर्वन्ति दिने दिने ।
आयुः प्रज्ञा बलं वीर्यं तेजस्तेषां च जायते ॥
ॐ नमः सवित्रे जगदेकचक्षुषे जगत्प्रसूतिस्थितिनाशहेतवे ।
त्रयीमयाय त्रिगुणात्मधारिणे विरिञ्चिनारायणशंकरात्मने ॥

॥ द्वादशोऽनुवाकः ॥

ॐ सूर्यं देवं नमस्यामि शरण्यं लोकसाक्षिणम् ।
लोचनं विश्वदेवानां सुरलोकप्रकाशकम् ॥
ॐ आराधयामि मित्रं सुरोत्तमं सर्वभावनम् ।
पूर्वदिक्पालकं भूप्रभुं ख्यातं भास्करमव्ययम् ॥

॥ त्रयोदशोऽनुवाकः ॥

ॐ सहस्रशीर्षा पुरुषः सहस्राक्षः सहस्रपात् ।
स भूमिं विश्वतो वृत्वाऽत्यतिष्ठद्दशाङ्गुलम् ॥
ॐ पुरुष एवेदं सर्वं यद्भूतं यच्च भव्यम् ।
उतामृतत्वस्येशानो यदन्नेनातिरोहति ॥
ॐ एतावानस्य महिमा अतो ज्यायाँश्च पूरुषः ।
पादोऽस्य विश्वा भूतानि त्रिपादस्यामृतं दिवि ॥

॥ चतुर्दशोऽनुवाकः ॥

ॐ आयुष्मन् भव ।
बलमसि बलाय त्वा ।
तेजोऽसि तेजसे त्वा ।
वर्चोऽसि वर्चसे त्वा ।
श्रियमावह जातवेदः ।
इन्द्रियमावह जातवेदः ।
प्रजामावह जातवेदः ।
रयिमावह जातवेदः ॥

॥ पञ्चदशोऽनुवाकः ॥

ॐ असतो मा सद्गमय ।
तमसो मा ज्योतिर्गमय ।
मृत्योर्माऽमृतं गमय ।
ॐ शान्तिः शान्तिः शान्तिः ॥

॥ षोडशोऽनुवाकः ॥

ॐ भूः पुनातु शिरः ।
भुवः पुनातु मुखम् ।
सुवः पुनातु ग्रीवाम् ।
महः पुनातु हृदयम् ।
जनः पुनातु नाभिम् ।
तपः पुनातु पादौ ।
सत्यं पुनातु पादतलम् ।
ॐ भूर्भुवः स्वः पुनातु माम् ॥

॥ सप्तदशोऽनुवाकः ॥

ॐ नमो ब्रह्मणे नमो अग्नये नमः पृथिव्यै नम ओषधीभ्यः ।
नमो वाचे नमो वाचस्पतये नमो विष्णवे बृहते करोमि ॥
ॐ नमस्त आयुधायानातताय धृष्णवे ।
उभाभ्यामुत ते नमो बाहुभ्यां तव धन्वने ॥

॥ अष्टादशोऽनुवाकः ॥

ॐ यज्ञेन यज्ञमयजन्त देवास् तानि धर्माणि प्रथमान्यासन् ।
ते ह नाकं महिमानः सचन्त यत्र पूर्वे साध्याः सन्ति देवाः ॥

॥ एकोनविंशोऽनुवाकः ॥

ॐ हिरण्यगर्भः समवर्तताग्रे भूतस्य जातः पतिरेक आसीत् ।
स दाधार पृथिवीं द्यामुतेमां कस्मै देवाय हविषा विधेम ॥
ॐ य आत्मदा बलदा यस्य विश्व उपासते प्रशिषं यस्य देवाः ।
यस्य छायामृतं यस्य मृत्युः कस्मै देवाय हविषा विधेम ॥

॥ विंशोऽनुवाकः ॥

ॐ यः प्राणतो निमिषतो महित्वा एक इद्राजा जगतो बभूव ।
य ईशे अस्य द्विपदश्चतुष्पदः कस्मै देवाय हविषा विधेम ॥
ॐ यस्येमे हिमवन्तो महित्वा यस्य समुद्रं रसया सहाहुः ।
यस्येमाः प्रदिशो यस्य बाहू कस्मै देवाय हविषा विधेम ॥

॥ एकविंशोऽनुवाकः ॥

ॐ आपः पुनन्तु पृथिवीं पृथिवी पूता पुनातु माम् ।
पुनन्तु ब्रह्मणस्पतिर्ब्रह्मपूता पुनातु माम् ।
यदुच्छिष्टमभोज्यं यद्वा दुश्चरितं मम ।
सर्वं पुनन्तु मामापो असतां च प्रतिग्रहं स्वाहा ॥

॥ द्वाविंशोऽनुवाकः ॥

ॐ अग्ने नय सुपथा राये अस्मान्
विश्वानि देव वयुनानि विद्वान् ।
युयोध्यस्मज्जुहुराणमेनो
भूयिष्ठां ते नमउक्तिं विधेम ॥

॥ फलश्रुतिः ॥

अरुणप्रश्नजपेन पापं नश्यति साधकः ।
आयुरारोग्यमैश्वर्यं लभते नात्र संशयः ।
सूर्यप्रसादाद्भक्तानां मनोवाञ्छा प्रसिद्ध्यति ॥
ॐ शान्तिः शान्तिः शान्तिः ॥""",
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
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.S | re.I)
    if not pre_match:
        return None
    raw = _strip_tags(pre_match.group(1))

    k, p, a = book, chapter, verse
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
            start = max(0, m.start() - 50)
            # Find the next section marker or end of document
            next_section = re.search(
                rf"॥\s*{k_dev}[।|\.]",
                raw[m.end():],
            )
            end = m.end() + next_section.start() if next_section else len(raw)
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
        url = "https://sanskritdocuments.org/doc_veda/vs.html"
        html = _get(url)
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.S | re.I)
    if not pre_match:
        return None
    raw = _strip_tags(pre_match.group(1))

    dev = {str(i): c for i, c in enumerate("०१२३४५६७८९")}
    ch_dev = "".join(dev.get(c, c) for c in chapter)
    next_ch = str(int(chapter) + 1)
    next_ch_dev = "".join(dev.get(c, c) for c in next_ch)

    patterns = [
        rf"अध्याय\s*{ch_dev}",
        rf"॥\s*{ch_dev}[।|\.]",
    ]
    for pat in patterns:
        m = re.search(pat, raw)
        if m:
            start = max(0, m.start() - 50)
            next_section = re.search(rf"अध्याय\s*{next_ch_dev}", raw[m.end():])
            end = m.end() + next_section.start() if next_section else len(raw)
            return raw[start:end].strip()
    return None


def _scrape_sanskritdocs_search(query):
    """Search sanskritdocuments.org for arbitrary Vedic/Sanskrit text."""
    encoded = urllib.parse.quote(query)
    url = f"https://sanskritdocuments.org/search/?q={encoded}"
    try:
        html = _get(url)
    except Exception:
        return None

    # Find links to document pages in search results
    links = re.findall(r'href="(/doc[^"]+\.html?)"', html, re.I)
    links = list(dict.fromkeys(links))  # deduplicate preserving order

    for link in links[:3]:
        doc_url = "https://sanskritdocuments.org" + link
        try:
            doc_html = _get(doc_url)
        except Exception:
            continue
        # Prefer <pre> blocks (plain Sanskrit text)
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", doc_html, re.S | re.I)
        if pre_match:
            text = _strip_tags(pre_match.group(1)).strip()
            if len(text) > 200:
                return text
        # Fall back to main content div
        for div_class in ["SanskritText", "devanagari", "content", "main"]:
            text = _extract(doc_html, "div", **{"class": div_class})
            if text and len(text) > 200:
                return text
    return None


def fetch_verse(ref, script):
    text_type, book, chapter, verse = _normalize_ref(ref)

    if text_type == "MANTRA":
        return KNOWN_MANTRAS.get(book)

    if text_type == "HYMN":
        cached = KNOWN_HYMNS.get(book)
        if cached:
            return cached
        # Not in local cache — search the web
        try:
            result = _scrape_sanskritdocs_search(ref)
            if result:
                return result
        except Exception:
            pass
        return None  # let handler fall through to Bedrock

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

    # Last resort: web search on sanskritdocuments.org
    try:
        result = _scrape_sanskritdocs_search(ref)
        if result:
            return result
    except Exception:
        pass
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
