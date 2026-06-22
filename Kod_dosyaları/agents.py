"""
agents.py — Ajan Mimarisi ve Muhakeme Motoru
=============================================
Üye 1'in tam geliştirme alanı.

Bu modül, Ajan Destekli Dinamik Pazar Analiz Sistemi'nin beyin katmanını
oluşturur. Beş uzman ajan ve bir orkestratörden oluşan bu yapı, kullanıcının
doğal dil girdisini rasyonel bir karar zincirine dönüştürür.

Ajan Hiyerarşisi:
    Consultant  → Doğal dili teknik spesifikasyona çevirir
    Scout       → Araçları yöneterek ham veri toplar
    Critic      → Yorumları normalize eder, güven skoru üretir
    Economist   → Fiyat ve pazar analizi yapar (hibrit bellek)
    Auditor     → Güvenlik ve anomali denetimi, risk skoru üretir
    Orchestrator→ Ajanları sıralı çalıştırır, final rapor üretir

Karar Formülü:
    Trust Score = ((0.6 * Uzman Puanı) + (0.4 * Kullanıcı Puanı))
                  / (1 + Risk Faktörü)
"""

from __future__ import annotations
import os
import json
import logging
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv() # .env içindeki API Key'i sisteme yükler

# Araçlar — Üye 2'nin mock yapıları (gerçeklerle bire bir değiştirilebilir)
from tools import (
    ALL_TOOLS,
    TOOL_MAP,
    mock_get_price_history,
    mock_scrape_reviews,
    mock_search_products,
    mock_verify_seller,
)

# ---------------------------------------------------------------------------
# Loglama Yapılandırması
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MarketAnalysis")


# ===========================================================================
# §1 — VERİ MODELLERİ (Ajanlar Arası İletişim Sözleşmesi)
# ===========================================================================

@dataclass
class TechnicalSpec:
    """
    Consultant ajanının çıktısı.
    Doğal dil → yapılandırılmış teknik gereksinim.
    """
    category: str                          # Ürün kategorisi (laptop, telefon…)
    primary_use_case: str                  # Birincil kullanım amacı
    budget_min: float                      # Minimum bütçe (TL)
    budget_max: float                      # Maksimum bütçe (TL)
    must_have: list[str]                   # Olması zorunlu özellikler
    nice_to_have: list[str]                # Olsa iyi olur özellikler
    deal_breakers: list[str]               # Kabul edilemez özellikler
    search_keywords: list[str]             # Scout için arama anahtar kelimeleri
    raw_query: str = ""                    # Orijinal kullanıcı girdisi

    def to_scout_query(self) -> str:
        """Scout ajanı için optimize edilmiş arama cümlesi üretir."""
        return f"{self.category} {' '.join(self.search_keywords[:3])}"


@dataclass
class ReviewAnalysis:
    """
    Critic ajanının çıktısı.
    Ham yorumları normalize edilmiş güven metriğine dönüştürür.
    """
    product_id: str
    raw_review_count: int                  # İşlenmeden önce toplam yorum
    filtered_review_count: int             # Lojistik şikayeti elendikten sonra
    logistics_complaint_ratio: float       # Elenen yorum oranı
    expert_score: float                    # Uzman/profesyonel inceleme puanı (0-5)
    user_score: float                      # Kullanıcı deneyimi puanı (0-5)
    normalized_sentiment: float            # Normalize edilmiş genel duygu (-1 ile 1)
    category_avg_score: float              # Kategori ortalaması (normalizasyon temeli)
    bias_correction_delta: float           # Negatiflik yanlılığı düzeltmesi
    trust_score: float = 0.0              # Hesaplanmış final güven skoru


@dataclass
class MarketAnalysis:
    """
    Economist ajanının çıktısı.
    Fiyat pozisyonlaması ve pazar durumu değerlendirmesi.
    """
    product_id: str
    current_price: float
    market_avg_price: float
    local_cached_price: Optional[float]    # SQLite'dan (Üye 3 hazır olunca)
    price_trend: str                       # "rising" | "falling" | "stable"
    price_percentile: float                # Ürünün fiyat dağılımındaki konumu
    is_fair_price: bool
    discount_potential: float              # Beklenen indirim olasılığı (0-1)
    market_status: str                     # "buyer_market" | "seller_market" | "balanced"
    price_history_volatility: float        # Fiyat istikrarsızlık skoru (0-1)
    recommendation: str                    # "buy_now" | "wait" | "avoid"


@dataclass
class SecurityAudit:
    """
    Auditor ajanının çıktısı.
    Platform güvenliği ve fiyat anomali riski.
    """
    product_id: str
    seller_id: str
    platform: str
    has_ssl: bool
    domain_age_days: int
    complaint_ratio: float
    price_anomaly_score: float             # 0=normal, 1=çok şüpheli
    is_price_dumping: bool                 # Piyasanın çok altında mı?
    is_price_gouging: bool                 # Piyasanın çok üstünde mi?
    risk_score: float                      # Final risk faktörü (0-1)
    risk_level: str                        # "low" | "medium" | "high" | "critical"
    blacklist_flags: list[str]             # Kara liste uyarıları


@dataclass
class FinalReport:
    """
    Orchestrator'ın nihai çıktısı.
    Tüm ajan sonuçlarını rasyonel tavsiyeye dönüştürür.
    """
    query: str
    spec: TechnicalSpec
    ranked_products: list[dict]            # Trust Score'a göre sıralanmış ürünler
    top_recommendation: dict               # En iyi öneri
    market_status_block: str              # Pazar durumu özeti
    blacklist_block: list[dict]           # Kara listeli satıcılar/ürünler
    rational_advice: str                  # Nihai rasyonel tavsiye metni
    overall_confidence: float             # Sistemin genel güven düzeyi


# ===========================================================================
# §2 — TEMEL AJAN SINIFI
# ===========================================================================

class BaseAgent:
    """
    Tüm ajanların türediği temel sınıf.
    Ortak LLM konfigürasyonu ve loglama altyapısını sağlar.

    Mimari Not:
        Her ajan kendi system_prompt'u ve temperature değeriyle özelleşir.
        temperature=0 → deterministik/analitik ajanlar (Critic, Auditor)
        temperature=0.3 → yaratıcı/yorumlayıcı ajanlar (Consultant)
    """

    def __init__(
        self,
        name: str,
        role: str,
        temperature: float = 0.0,
        model: str = "gpt-4o-mini",
    ):
        self.name = name
        self.role = role
        self.logger = logging.getLogger(f"Agent.{name}")

        # NOT: Gerçek kullanımda API anahtarı environment variable'dan gelir.
        # Şu an LLM çağrısı mock olarak simüle edilmektedir.
        # self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.llm = None  # Mock mod — LLM bağımlılığı kaldırıldı

        self.logger.info(f"'{name}' ajanı başlatıldı. Rol: {role}")

    def _log_step(self, step: str, detail: str = ""):
        self.logger.info(f"[{self.name}] {step}" + (f" → {detail}" if detail else ""))

    def _parse_json_response(self, raw: str) -> dict:
        """LLM çıktısından JSON bloğunu güvenli şekilde ayıklar."""
        try:
            # Markdown kod bloğu varsa temizle
            cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip("` \n")
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON parse hatası: {e}. Ham metin: {raw[:200]}")
            return {}


# ===========================================================================
# §3 — CONSULTANT AJANI
# ===========================================================================

class ConsultantAgent(BaseAgent):
    """
    Doğal Dil → Teknik Spesifikasyon Dönüştürücüsü

    Muhakeme Zinciri:
        1. Kullanıcı ihtiyacını ayrıştır (use case extraction)
        2. Bütçe sınırlarını tespit et (explicit veya implicit)
        3. Öncelik hiyerarşisi oluştur (must_have vs nice_to_have)
        4. Kısıtları olumsuzdan olumluya çevir (deal_breaker tespiti)
        5. Scout için optimize edilmiş anahtar kelimeler üret
    """

    # Kategori → yaygın teknik özellikler eşlemesi
    CATEGORY_FEATURE_MAP = {
        "laptop": ["işlemci", "RAM", "depolama", "ekran", "pil", "grafik kartı", "ağırlık"],
        "telefon": ["işlemci", "RAM", "kamera", "batarya", "ekran boyutu", "depolama", "5G"],
        "tablet": ["ekran", "işlemci", "depolama", "batarya", "bağlantı", "kalem desteği"],
        "kulaklık": ["ses kalitesi", "ANC", "bağlantı tipi", "pil", "konfor", "mikrofon"],
        "televizyon": ["ekran boyutu", "çözünürlük", "panel tipi", "akıllı özellikler", "HDR"],
    }

    # Kullanım durumu → özellik öncelikleri eşlemesi
    USE_CASE_PRIORITY_MAP = {
        "oyun": {"must_have": ["güçlü GPU", "yüksek RAM"], "nice_to_have": ["yüksek ekran yenileme hızı"]},
        "iş": {"must_have": ["uzun pil ömrü", "hafif"], "nice_to_have": ["LTE", "geniş ekran"]},
        "öğrenci": {"must_have": ["uygun fiyat", "dayanıklı"], "nice_to_have": ["dokunmatik ekran"]},
        "video düzenleme": {"must_have": ["güçlü CPU", "renk doğruluğu", "geniş depolama"], "nice_to_have": ["Thunderbolt"]},
        "genel kullanım": {"must_have": ["denge"], "nice_to_have": ["hafif", "iyi pil"]},
    }

    def __init__(self):
        super().__init__(
            name="Consultant",
            role="Kullanıcı ihtiyaç analisti ve teknik gereksinim dönüştürücüsü",
            temperature=0.1, # daha rasyonel ve tutarlı cevaplar için idealdir
        )
        # Gemini 1.5 Flash bağlantısı
        self.llm = ChatGroq(
            model_name="llama-3.3-70b-versatile", # Gemini Flash'tan çok daha güçlü bir model
            groq_api_key=os.getenv("GROQ_API_KEY")
        )

        # LangChain PromptTemplate (gerçek LLM entegrasyonu için hazır)
        # Şık ve Profesyonel Prompt Tanımı
        self.spec_extraction_prompt = PromptTemplate(
            input_variables=["user_query"],
            template="""
            Sen uzman bir satın alma danışmanısın. Kullanıcının şu isteğini analiz et: "{user_query}"

            Analizini yaparken şunlara dikkat et:
            1. İsteği teknik parametrelere çevir (Örn: "Şarjı iyi gitsin" -> 5000mAh+).
            2. Pazar taraması için en etkili 3 adet GERÇEK ürün modelini belirle.
            3. Arama motoru için temiz anahtar kelimeler üret.

            SADECE AŞAĞIDAKİ JSON FORMATINDA CEVAP VER:
            {{
                "category": "kategori adı",
                "primary_use_case": "kullanım amacı",
                "budget_min": min_tl,
                "budget_max": max_tl,
                "must_have": ["özellik1", "özellik2"],
                "nice_to_have": ["özellik1"],
                "search_keywords": ["model1", "model2", "temiz_sorgu"]
            }}
            """
        )
    
    def analyze(self, user_query: str) -> TechnicalSpec:
        self._log_step("Analiz başlıyor (Gemini AI)", user_query[:80])

        # ── TEK ADIM: LLM Analizi ─────────────────────────────────────────
        # Prompt'u doldur ve Gemini'a gönder
        formatted_prompt = self.spec_extraction_prompt.format(user_query=user_query)
        response = self.llm.invoke(formatted_prompt)
        
        try:
            # JSON temizleme (LLM bazen ```json ekleyebiliyor)
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            # Arama kelimelerinin en başına her zaman orijinal sorguyu ekle (Güvenlik önlemi)
            keywords = data.get("search_keywords", [])
            if user_query not in keywords:
                keywords.insert(0, user_query)

            # TechnicalSpec nesnesini oluştur ve döndür
            spec = TechnicalSpec(
                category=data.get("category", "elektronik"),
                primary_use_case=data.get("primary_use_case", "genel"),
                budget_min=float(data.get("budget_min", 1500)),
                budget_max=float(data.get("budget_max", 5000)),
                must_have=data.get("must_have", []),
                nice_to_have=data.get("nice_to_have", []),
                deal_breakers=[], # LLM isterse buraya da ekleme yapabilir
                search_keywords=keywords,
                raw_query=user_query
            )

            self._log_step("Spesifikasyon üretildi", f"Kategori: {spec.category}")
            return spec

        except Exception as e:
            self._log_step("Hata oluştu, fallback'e geçiliyor", str(e))
            # Hata durumunda sistemin çökmemesi için basit bir nesne dön
            return TechnicalSpec(category="elektronik", search_keywords=[user_query], raw_query=user_query)

    # ── Yardımcı Metodlar ────────────────────────────────────────────────

    def _detect_category(self, query: str) -> str:
        keyword_map = {
            "laptop": ["laptop", "bilgisayar", "notebook", "macbook", "dizüstü"],
            "telefon": ["telefon", "smartphone", "iphone", "samsung", "android"],
            "tablet": ["tablet", "ipad"],
            "kulaklık": ["kulaklık", "headphone", "earbuds", "airpods"],
            "televizyon": ["televizyon", "tv", "monitör"],
            "modem": ["modem", "router", "vDSL", "fiber"],
            "klavye": ["klavye", "keyboard", "mekanik klavye"]
        }
        for category, keywords in keyword_map.items():
            if any(kw in query for kw in keywords):
                return category
        return "elektronik"

    def _detect_use_case(self, query: str) -> str:
        use_case_keywords = {
            "oyun": ["oyun", "gaming", "game", "fps", "fortnite", "valorant"],
            "iş": ["iş", "ofis", "toplantı", "sunum", "excel", "word"],
            "öğrenci": ["öğrenci", "okul", "üniversite", "ders"],
            "video düzenleme": ["video", "düzenleme", "editing", "premiere", "davinci"],
        }
        for use_case, keywords in use_case_keywords.items():
            if any(kw in query for kw in keywords):
                return use_case
        return "genel kullanım"

    def _extract_budget(self, query: str) -> tuple[float, float]:
        """
        Bütçe çıkarımı — dil kalıplarını işler:
          "3000 TL altında", "5000₺'ye kadar", "2-4 bin lira arası"
        """
        # "X TL altında" / "X₺'ye kadar"
        under_pattern = re.search(r"(\d[\d\.,]*)\s*(?:tl|₺|lira)?\s*(?:altında|'ye kadar|kadar)", query)
        if under_pattern:
            budget_max = float(under_pattern.group(1).replace(".", "").replace(",", ""))
            return budget_max * 0.5, budget_max

        # "X-Y bin" veya "X ile Y TL arası"
        range_pattern = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:bin|tl|₺|lira)", query)
        if range_pattern:
            low = float(range_pattern.group(1).replace(".", ""))
            high = float(range_pattern.group(2).replace(".", ""))
            if high < 100:  # "2-4 bin" formatı
                low *= 1000
                high *= 1000
            return low, high

        # Sadece sayı + birim
        price_pattern = re.search(r"(\d[\d\.,]*)\s*(?:bin|tl|₺|lira)", query)
        if price_pattern:
            price = float(price_pattern.group(1).replace(".", "").replace(",", ""))
            if price < 100:
                price *= 1000
            return price * 0.7, price * 1.2

        # Varsayılan: orta segment
        return 1500.0, 5000.0

    def _extract_deal_breakers(self, query: str) -> list[str]:
        deal_breakers = []
        if any(kw in query for kw in ["ağır olmasın", "hafif", "taşınabilir"]):
            deal_breakers.append(">2.0kg")
        if any(kw in query for kw in ["çirkin", "büyük olmayan", "kompakt"]):
            deal_breakers.append("büyük kasa tasarımı")
        return deal_breakers

    def _extract_negative_constraints(self, query: str) -> list[str]:
        constraints = []
        negation_map = {
            "fan sesi": "yüksek fan gürültüsü",
            "ısınma": "aşırı ısınma sorunu",
            "yavaş": "düşük performans",
            "şarj sorunu": "kötü batarya ömrü",
        }
        for trigger, constraint in negation_map.items():
            if trigger in query:
                constraints.append(constraint)
        return constraints

    def _generate_search_keywords(self, category: str, use_case: str, budget_max: float, user_query: str) -> list[str]:
        """
        Sorguyu dinamik olarak zenginleştirir. 
        Tekrarı önler ve sadece katma değer sağlayan kelimeleri ekler.
        """
        """
        keywords = [category]
        if use_case != "genel kullanım":
            keywords.append(use_case)
        if budget_max < 3000:
            keywords.append("uygun fiyatlı")
        elif budget_max > 10000:
            keywords.append("premium")
        keywords.extend(self.CATEGORY_FEATURE_MAP.get(category, [])[:2])
        return keywords[:6]
        """
        """
        Arama motorları için en yalın ve etkili kelimeyi döndürür.
        Analiz bilgilerini (kategori, bütçe vb.) search query'ye KATMAMA kararı aldık.
        """
        # 1. ÇIKIŞ NOKTASI: Her zaman kullanıcının orijinal sorgusu (En güvenilir veri)
        keywords = [user_query] 

        # 2. KATEGORİ EKLEME: 
        # Eğer kategori, kullanıcının yazdığı metnin içinde zaten geçmiyorsa ekle.
        # (Örn: Kullanıcı "Logitech" yazdıysa "klavye" eklemek mantıklı, 
        # ama zaten "Logitech Klavye" yazdıysa tekrar "klavye" eklemek aptallıktır.)
        if category and category.lower() not in user_query.lower():
            # "elektronik" gibi çok genel ve arama sonucunu bozan kelimeleri 
            # bir 'black_list' üzerinden kontrol etmek daha profesyoneldir.
            GENERAL_TERMS = ["elektronik", "ürün", "cihaz", "genel"]
            if category not in GENERAL_TERMS:
                keywords.append(category)

        # 3. USE CASE (KULLANIM AMACI):
        # Sadece 'genel kullanım' dışındaki spesifik senaryoları ekle.
        if use_case not in ["genel kullanım", "standart"]:
            keywords.append(use_case)

        # 4. TEKNİK ÖZELLİKLER:
        # Sadece kategoriye özgü, aramayı daraltacak ilk 2 özelliği ekle.
        category_features = self.CATEGORY_FEATURE_MAP.get(category, [])
        for feature in category_features[:2]:
            if feature.lower() not in user_query.lower():
                keywords.append(feature)

        # 5. TEMİZLİK: Duplicate (tekrar eden) kelimeleri koruyarak listeyi eşsiz yap
        # (Python 3.7+ dict.fromkeys sırayı bozmadan unique yapar)
        return list(dict.fromkeys(keywords))


# ===========================================================================
# §4 — SCOUT AJANI
# ===========================================================================

class ScoutAgent(BaseAgent):
    """
    Heterojen Kaynaklardan Veri Toplayıcı

    Sorumluluklar:
        - E-ticaret platformlarında ürün arama
        - Forum ve video altyazılarından yorum toplama
        - Fiyat geçmişi çekme
        - Ham veriyi yapılandırılmış formata dönüştürme

    Araç Kullanım Stratejisi:
        1. Paralel kaynak sorgulaması (mock'ta sıralı)
        2. Yeterli sonuç yoksa sorguyu genişlet
        3. Her veri kaynağını kaynak-tipi ile etiketle
    """

    MINIMUM_PRODUCT_COUNT = 3

    def __init__(self):
        super().__init__(
            name="Scout",
            role="Pazar veri toplayıcısı ve heterojen kaynak yöneticisi",
            temperature=0.0,
        )

    def gather(self, spec: TechnicalSpec) -> dict:
        """
        TechnicalSpec'e göre veri toplar.
        Çıktı: { "products": [...], "reviews": {...}, "price_histories": {...} }
        """
        self._log_step("Veri toplama başlıyor", spec.to_scout_query())

        # ── ADIM 1: Ürün Arama ──────────────────────────────────────────
        products = self._search_products(spec)
        self._log_step("Ürün arama tamamlandı", f"{len(products)} ürün")

        # ── ADIM 2: Yorum Toplama (her ürün için) ───────────────────────
        reviews: dict[str, list] = {}
        for product in products[:5]:  # İlk 5 ürünle sınırla
            product_id = product["id"]
            reviews[product_id] = self._scrape_reviews(product_id)
            self._log_step("Yorumlar toplandı", f"{product_id}: {len(reviews[product_id])} yorum")

        # ── ADIM 3: Fiyat Geçmişi ───────────────────────────────────────
        price_histories: dict[str, list] = {}
        for product in products[:5]:
            product_id = product["id"]
            price_histories[product_id] = self._get_price_history(product_id)

        self._log_step("Tüm veriler toplandı")
        return {
            "products": products,
            "reviews": reviews,
            "price_histories": price_histories,
            "spec": spec,
        }

    # ── Araç Çağrı Metodları ────────────────────────────────────────────

    def _search_products(self, spec: TechnicalSpec) -> list[dict]:
        # ── ADIM 1: İlk Arama (Daha sade sorgu ile) ──────────────────────
        # spec.to_scout_query() bazen çok uzun olup 0 sonuç verebiliyor. 
        # İlk 2 anahtar kelime genelde en iyi sonucu verir.
        query = " ".join(spec.search_keywords[:2]) 
    
        raw = mock_search_products(
            query=query,
            max_results=10,
            min_price=spec.budget_min,
            max_price=spec.budget_max,
        )
    
        result = json.loads(raw)
        products = result.get("sonuclar", result.get("product_data", []))

        # ── ADIM 2: Yetersiz Sonuç Varsa Genişlet ───────────────────────
        if len(products) < self.MINIMUM_PRODUCT_COUNT:
            self._log_step("Yetersiz sonuç, sorgu genişletiliyor", spec.category)
            raw_expanded = mock_search_products(query=spec.category, max_results=10)
            expanded_data = json.loads(raw_expanded)
            products = expanded_data.get("sonuclar", expanded_data.get("product_data", []))

        # ── ADIM 3: VERİ NORMALİZASYONU (Hayati Kısım!) ──────────────────
        # Bu döngü 'KeyError: price' hatasını bitiren yerdir.
        normalized_list = []
        for i, p in enumerate(products):
            std_product = {
                # 'id' yoksa URL'yi, o da yoksa indeksi kullan
                "id": p.get("id", p.get("url", f"prod_{i}")),
                "name": p.get("urun_adi", "Bilinmeyen Ürün"),
                # 'fiyat' anahtarını 'price' yapıyoruz (float garantisiyle)
                "price": float(p.get("fiyat", p.get("price", 0.0))), 
                "source": p.get("kaynak", "web"),
                "rating": float(p.get("puan", 0.0)),
                "review_count": int(p.get("yorum_sayisi", 0)),
                "url": p.get("url", "")
            }
            normalized_list.append(std_product)

        return normalized_list
    
    def _scrape_reviews(self, product_id: str) -> list[dict]:
        raw = mock_scrape_reviews(
            product_id=product_id,
            sources=["e-commerce", "forum", "video"],
        )
        return json.loads(raw).get("product_data", [])

    def _get_price_history(self, product_id: str, days: int = 30) -> list[dict]:
        raw = mock_get_price_history(product_id=product_id, days=days)
        return json.loads(raw).get("product_data", [])


# ===========================================================================
# §5 — CRITIC AJANI
# ===========================================================================

class CriticAgent(BaseAgent):
    """
    Yorum Normalizasyonu ve Güven Skoru Üreticisi

    Muhakeme Zinciri:
        1. Lojistik şikayetlerini elemek
           → "kargo geç geldi", "paket açıktı" → ürün kalitesini yansıtmaz
        2. Negatiflik yanlılığını tespit et ve düzelt
           → İnsanlar olumsuz deneyimleri %3x daha fazla yazar
        3. Uzman (profesyonel) vs kullanıcı yorumlarını ayır
        4. Kategori ortalamasına göre normalize et
        5. Hibrit güven skoru hesapla

    Trust Score Formülü:
        Trust Score = ((0.6 * Uzman Puanı) + (0.4 * Kullanıcı Puanı))
                      / (1 + Risk Faktörü)
    """

    # Lojistik şikayetleri için anahtar kelimeler
    LOGISTICS_KEYWORDS = {
        "kargo", "teslimat", "paket", "ambalaj", "kurye", "gönderim",
        "gecikme", "hasar", "yırtık", "kutu", "delivery", "shipping",
        "paketleme", "iade", "değişim süreci",
    }

    # Negatiflik yanlılığı düzeltme katsayısı (araştırma tabanlı)
    NEGATIVITY_BIAS_CORRECTION = 0.15

    # Kategori varsayılan ortalama puanları (Üye 3'ün DB'si hazır olunca oradan gelecek)
    CATEGORY_BASELINES = {
        "laptop": 3.8,
        "telefon": 3.9,
        "tablet": 4.0,
        "kulaklık": 4.1,
        "televizyon": 3.7,
        "elektronik": 3.8,
    }

    def __init__(self):
        super().__init__(
            name="Critic",
            role="Yorum analisti, negatiflik yanlılığı düzelticisi, güven skoru üreticisi",
            temperature=0.0,
        )

    def analyze(
        self,
        product_id: str,
        reviews: list[dict],
        category: str,
        risk_factor: float = 0.0,
    ) -> ReviewAnalysis:
        """
        Yorum listesini işleyerek ReviewAnalysis üretir.
        risk_factor: Auditor ajanından gelir (döngüsel bağımlılıktan kaçınmak için
                     önce 0.0 ile çağrılır, Auditor çalıştıktan sonra trust_score güncellenir).
        """
        self._log_step("Yorum analizi başlıyor", f"product={product_id}, {len(reviews)} yorum")
        raw_count = len(reviews)

        # ── ADIM 1: Lojistik Şikayeti Eleme ────────────────────────────
        product_reviews = self._filter_logistics_complaints(reviews)
        logistics_ratio = (raw_count - len(product_reviews)) / max(raw_count, 1)
        self._log_step(
            "Lojistik eleme",
            f"{raw_count - len(product_reviews)} yorum elendi ({logistics_ratio:.1%})"
        )

        # ── ADIM 2: Uzman / Kullanıcı Ayrımı ───────────────────────────
        expert_reviews = [r for r in product_reviews if r.get("source") == "video"]
        user_reviews = [r for r in product_reviews if r.get("source") != "video"]

        # ── ADIM 3: Ham Puanları Hesapla ────────────────────────────────
        raw_expert_score = self._compute_weighted_average([r.get("rating", 3.0) for r in expert_reviews])
        raw_user_score = self._compute_weighted_average([r.get("rating", 3.0) for r in user_reviews])

        # ── ADIM 4: Negatiflik Yanlılığı Düzeltmesi ─────────────────────
        # Mantık: Kullanıcı yorumlarında negatif deneyimler aşırı temsil edilir.
        # Düzeltme: negatif yorumların ağırlığını %15 azalt.
        negative_ratio = self._compute_negative_ratio(product_reviews)
        bias_correction = self.NEGATIVITY_BIAS_CORRECTION * negative_ratio
        corrected_user_score = min(5.0, raw_user_score + bias_correction)

        self._log_step(
            "Yanlılık düzeltmesi",
            f"ham={raw_user_score:.2f} → düzeltilmiş={corrected_user_score:.2f} (delta={bias_correction:.3f})"
        )

        # ── ADIM 5: Kategori Ortalamasına Göre Normalizasyon ────────────
        category_avg = self.CATEGORY_BASELINES.get(category, 3.8)
        normalized_sentiment = self._normalize_to_category(corrected_user_score, category_avg)

        # ── ADIM 6: Uzman Puanı (uzman yorum yoksa kullanıcı puanıyla tahmini doldur) ──
        if not expert_reviews:
            expert_score = min(5.0, corrected_user_score + 0.1)  # Hafif iyimser tahmin
            self._log_step("Uzman yorumu bulunamadı, tahminsel puan kullanıldı")
        else:
            expert_score = raw_expert_score

        # ── ADIM 7: Trust Score Hesabı ──────────────────────────────────
        trust_score = self._compute_trust_score(
            expert_score=expert_score,
            user_score=corrected_user_score,
            risk_factor=risk_factor,
        )

        analysis = ReviewAnalysis(
            product_id=product_id,
            raw_review_count=raw_count,
            filtered_review_count=len(product_reviews),
            logistics_complaint_ratio=logistics_ratio,
            expert_score=round(expert_score, 3),
            user_score=round(corrected_user_score, 3),
            normalized_sentiment=round(normalized_sentiment, 3),
            category_avg_score=category_avg,
            bias_correction_delta=round(bias_correction, 3),
            trust_score=round(trust_score, 3),
        )

        self._log_step("Analiz tamamlandı", f"Trust Score = {trust_score:.3f}")
        return analysis

    def update_trust_score_with_risk(self, analysis: ReviewAnalysis, risk_factor: float) -> ReviewAnalysis:
        """
        Auditor ajanının risk skoru netleştikten sonra trust_score'u günceller.
        Bu metod Orchestrator tarafından iki aşamalı hesaplama döngüsünde çağrılır.
        """
        analysis.trust_score = round(
            self._compute_trust_score(analysis.expert_score, analysis.user_score, risk_factor),
            3,
        )
        self._log_step(
            f"Trust Score risk ile güncellendi",
            f"risk={risk_factor:.3f} → trust={analysis.trust_score:.3f}",
        )
        return analysis

    # ── Yardımcı Metodlar ────────────────────────────────────────────────

    def _filter_logistics_complaints(self, reviews: list[dict]) -> list[dict]:
        """Lojistik şikayeti içeren yorumları eleyerek ürün yorumlarını döndürür."""
        def is_logistics(review: dict) -> bool:
            # Kaynak bazlı eleme: e-ticaret lojistik oranı daha yüksek
            if review.get("is_logistics_complaint"):
                return True
            text = review.get("text", "").lower()
            return any(kw in text for kw in self.LOGISTICS_KEYWORDS)

        return [r for r in reviews if not is_logistics(r)]

    def _compute_weighted_average(self, scores: list[float]) -> float:
        """Boş liste için kategori ortalaması döndürür."""
        if not scores:
            return 3.8
        return statistics.mean(scores)

    def _compute_negative_ratio(self, reviews: list[dict]) -> float:
        """Negatif yorum oranını hesaplar."""
        if not reviews:
            return 0.0
        negative_count = sum(
            1 for r in reviews
            if r.get("sentiment") == "negative" or r.get("rating", 3) < 3.0
        )
        return negative_count / len(reviews)

    def _normalize_to_category(self, score: float, category_avg: float) -> float:
        """
        Puanı kategori ortalamasına göre normalize eder.
        Çıktı: [-1, 1] aralığında normalize duygu skoru
        """
        delta = score - category_avg
        # Maksimum sapma 5 puan üzerinden normalize
        return max(-1.0, min(1.0, delta / 2.5))

    def _compute_trust_score(
        self,
        expert_score: float,
        user_score: float,
        risk_factor: float,
    ) -> float:
        """
        Temel karar formülü:
            Trust Score = ((0.6 * Uzman Puanı) + (0.4 * Kullanıcı Puanı))
                          / (1 + Risk Faktörü)

        Puanlar 0-5 arasında, Risk Faktörü 0-1 arasında.
        Sonuç 0-5 arasında yorumlanır.
        """
        weighted_score = (0.6 * expert_score) + (0.4 * user_score)
        trust = weighted_score / (1.0 + risk_factor)
        return round(min(5.0, max(0.0, trust)), 3)


# ===========================================================================
# §6 — ECONOMIST AJANI
# ===========================================================================

class EconomistAgent(BaseAgent):
    """
    Pazar Analizi ve Fiyat Pozisyonlama Uzmanı

    Muhakeme Zinciri:
        1. Fiyat geçmişinden trend hesapla (rising/falling/stable)
        2. Yerel SQLite önbelleği ile dış fiyatı karşılaştır (hibrit bellek)
        3. Pazar dağılımındaki yüzdelik dilimi hesapla
        4. Pazar durumunu sınıflandır (alıcı/satıcı pazarı)
        5. Satın alma zamanlaması tavsiyesi üret

    Hibrit Bellek Stratejisi:
        - Önce SQLite'dan (Üye 3) fiyat çek
        - Yoksa dış kaynak fiyatını kullan
        - Her iki fiyat da varsa ağırlıklı ortalama al (0.4 yerel + 0.6 dış)
    """

    # Fiyat anomali eşikleri
    PRICE_TREND_THRESHOLD = 0.03   # %3'ten fazla değişim = trend
    BUYER_MARKET_THRESHOLD = 0.40  # Ürünlerin %40'ı ortalamanın altında → alıcı pazarı
    VOLATILITY_HIGH = 0.08          # %8+ volatilite = yüksek oynaklık

    def __init__(self):
        super().__init__(
            name="Economist",
            role="Pazar analisti, fiyat pozisyonlama ve satın alma zamanlama uzmanı",
            temperature=0.0,
        )
        # Üye 3 DB bağlantısı (hazır olunca aktif edilecek)
        # from database import DatabaseManager
        # self.db = DatabaseManager()

    def analyze(
        self,
        product: dict,
        price_history: list[dict],
        all_products: list[dict],
        category: str,
    ) -> MarketAnalysis:
        """Tek ürün için pazar analizi üretir."""
        product_id = product["id"]
        current_price = product["price"]
        self._log_step("Ekonomi analizi başlıyor", f"{product_id} @ {current_price:.2f}₺")

        # ── ADIM 1: Hibrit Fiyat Belirleme ──────────────────────────────
        local_cached_price = self._get_local_price(product_id)
        effective_price = self._compute_effective_price(current_price, local_cached_price)

        # ── ADIM 2: Fiyat Geçmişi Analizi ───────────────────────────────
        price_trend, volatility = self._analyze_price_trend(price_history)
        self._log_step("Trend analizi", f"trend={price_trend}, volatilite={volatility:.3f}")

        # ── ADIM 3: Piyasa Pozisyonu ─────────────────────────────────────
        all_prices = [p["price"] for p in all_products if "price" in p]
        market_avg = statistics.mean(all_prices) if all_prices else effective_price
        percentile = self._compute_percentile(effective_price, all_prices)
        self._log_step("Piyasa pozisyonu", f"percentile={percentile:.1%}, avg={market_avg:.2f}₺")

        # ── ADIM 4: Piyasa Durumu Sınıflandırması ───────────────────────
        market_status = self._classify_market(all_prices, market_avg)

        # ── ADIM 5: İndirim Potansiyeli ─────────────────────────────────
        discount_potential = self._estimate_discount_potential(price_trend, volatility, market_status)

        # ── ADIM 6: Satın Alma Zamanlaması ──────────────────────────────
        recommendation = self._generate_timing_recommendation(
            price_trend, percentile, discount_potential, volatility
        )

        is_fair = 0.3 <= percentile <= 0.7

        analysis = MarketAnalysis(
            product_id=product_id,
            current_price=round(effective_price, 2),
            market_avg_price=round(market_avg, 2),
            local_cached_price=local_cached_price,
            price_trend=price_trend,
            price_percentile=round(percentile, 3),
            is_fair_price=is_fair,
            discount_potential=round(discount_potential, 3),
            market_status=market_status,
            price_history_volatility=round(volatility, 3),
            recommendation=recommendation,
        )

        self._log_step("Analiz tamamlandı", f"öneri={recommendation}, adil={is_fair}")
        return analysis

    # ── Yardımcı Metodlar ────────────────────────────────────────────────

    def _get_local_price(self, product_id: str) -> Optional[float]:
        """
        SQLite'dan önbelleklenmiş fiyatı çeker.
        Üye 3'ün DB implementasyonu tamamlanana kadar None döner.
        """
        try:
            # TODO (Üye 3): return self.db.get_cached_price(product_id)
            return None
        except Exception:
            return None

    def _compute_effective_price(self, external_price: float, local_price: Optional[float]) -> float:
        """
        Hibrit fiyat hesaplama:
            Yerel fiyat varsa: %40 yerel + %60 dış kaynak
            Yoksa: sadece dış kaynak
        """
        if local_price is not None:
            blended = (0.4 * local_price) + (0.6 * external_price)
            self._log_step(
                "Hibrit fiyat",
                f"yerel={local_price:.2f} + dış={external_price:.2f} → {blended:.2f}"
            )
            return blended
        return external_price

    def _analyze_price_trend(self, history: list[dict]) -> tuple[str, float]:
        """Fiyat geçmişinden trend ve volatilite hesaplar."""
        if len(history) < 3:
            return "stable", 0.0

        prices = [h["price"] for h in history]
        first_half = statistics.mean(prices[:len(prices)//2])
        second_half = statistics.mean(prices[len(prices)//2:])
        change_ratio = (second_half - first_half) / first_half

        if change_ratio > self.PRICE_TREND_THRESHOLD:
            trend = "rising"
        elif change_ratio < -self.PRICE_TREND_THRESHOLD:
            trend = "falling"
        else:
            trend = "stable"

        # Volatilite: normalize standart sapma
        if len(prices) >= 2:
            std_dev = statistics.stdev(prices)
            volatility = std_dev / statistics.mean(prices)
        else:
            volatility = 0.0

        return trend, volatility

    def _compute_percentile(self, price: float, all_prices: list[float]) -> float:
        """Fiyatın dağılımdaki yüzdelik konumunu hesaplar."""
        if not all_prices:
            return 0.5
        below = sum(1 for p in all_prices if p <= price)
        return below / len(all_prices)

    def _classify_market(self, all_prices: list[float], avg: float) -> str:
        if not all_prices:
            return "balanced"
        below_avg = sum(1 for p in all_prices if p < avg) / len(all_prices)
        if below_avg > 0.6:
            return "buyer_market"
        elif below_avg < 0.4:
            return "seller_market"
        return "balanced"

    def _estimate_discount_potential(
        self, trend: str, volatility: float, market_status: str
    ) -> float:
        """İndirim olasılığını [0-1] aralığında tahmin eder."""
        base = 0.2
        if trend == "falling":
            base += 0.3
        if market_status == "buyer_market":
            base += 0.2
        if volatility > self.VOLATILITY_HIGH:
            base += 0.15
        return min(1.0, base)

    def _generate_timing_recommendation(
        self,
        trend: str,
        percentile: float,
        discount_potential: float,
        volatility: float,
    ) -> str:
        """
        Satın alma zamanlaması mantığı:
            - Fiyat yüksek ve düşüyor → bekle
            - Fiyat düşük ve stabil → şimdi al
            - Yüksek volatilite → riskli, kaçın veya bekle
        """
        if volatility > 0.12:
            return "avoid"
        if percentile > 0.7 and trend == "falling":
            return "wait"
        if percentile < 0.4 and trend in ("stable", "falling"):
            return "buy_now"
        if discount_potential > 0.5:
            return "wait"
        return "buy_now"


# ===========================================================================
# §7 — AUDITOR AJANI
# ===========================================================================

class AuditorAgent(BaseAgent):
    """
    Güvenlik Denetimi ve Risk Skorlaması

    Denetlenen Faktörler:
        1. Site güvenliği: SSL sertifikası, alan adı yaşı
        2. Satıcı güvenilirliği: şikayet oranı, kayıt süresi
        3. Fiyat anomalisi: dump fiyat (çok ucuz) veya fahiş fiyat (çok pahalı)
        4. Kara liste kontrol: Üye 3'ün DB'sinden

    Risk Skoru Bileşenleri (ağırlıklı):
        - SSL Yokluğu: +0.30
        - Genç Alan Adı (<365 gün): +0.25
        - Yüksek Şikayet Oranı (>%10): +0.20
        - Fiyat Dumping (<piyasa ortalaması %40 altı): +0.35
        - Fahiş Fiyat (>piyasa ortalaması %80 üstü): +0.20
        - Doğrulanmamış Satıcı: +0.15
    """

    # Anomali eşikleri
    PRICE_DUMP_THRESHOLD = 0.40      # Ortalamanın %40 altı → dump
    PRICE_GOUGE_THRESHOLD = 0.80     # Ortalamanın %80 üstü → fahiş
    HIGH_COMPLAINT_THRESHOLD = 0.10  # %10 şikayet oranı
    YOUNG_DOMAIN_THRESHOLD = 365     # 1 yıldan genç alan

    RISK_LEVELS = {
        (0.0, 0.20): "low",
        (0.20, 0.45): "medium",
        (0.45, 0.70): "high",
        (0.70, 1.01): "critical",
    }

    def __init__(self):
        super().__init__(
            name="Auditor",
            role="Güvenlik denetçisi, fiyat anomali dedektifi, risk sınıflandırıcısı",
            temperature=0.0,
        )

    def audit(
        self,
        product: dict,
        market_avg: float,
    ) -> SecurityAudit:
        """Ürün ve satıcı için güvenlik denetimi yapar."""
        product_id = product["id"]
        seller_id = product.get("source", "unknown_seller")
        platform = product.get("source", "unknown")

        self._log_step("Güvenlik denetimi başlıyor", f"{product_id} @ {platform}")

        # ── ADIM 1: Satıcı Doğrulama ────────────────────────────────────
        seller_data = self._verify_seller(seller_id, platform)

        # ── ADIM 2: Fiyat Anomali Tespiti ───────────────────────────────
        price = product["price"]
        is_dumping = price < market_avg * (1 - self.PRICE_DUMP_THRESHOLD)
        is_gouging = price > market_avg * (1 + self.PRICE_GOUGE_THRESHOLD)
        price_anomaly_score = self._compute_price_anomaly_score(price, market_avg)

        self._log_step(
            "Fiyat anomalisi",
            f"dump={is_dumping}, fahiş={is_gouging}, anomali={price_anomaly_score:.3f}"
        )

        # ── ADIM 3: Risk Skoru Bileşenleri ──────────────────────────────
        risk_components = []
        blacklist_flags = []

        if not seller_data.get("has_ssl", True):
            risk_components.append(0.30)
            blacklist_flags.append("SSL sertifikası eksik")

        if seller_data.get("domain_age_days", 9999) < self.YOUNG_DOMAIN_THRESHOLD:
            risk_components.append(0.25)
            blacklist_flags.append(f"Alan adı çok genç ({seller_data['domain_age_days']} gün)")

        complaint_ratio = seller_data.get("complaint_ratio", 0.0)
        if complaint_ratio > self.HIGH_COMPLAINT_THRESHOLD:
            risk_components.append(0.20)
            blacklist_flags.append(f"Yüksek şikayet oranı (%{complaint_ratio*100:.1f})")

        if is_dumping:
            risk_components.append(0.35)
            blacklist_flags.append("Şüpheli düşük fiyat (dump)")

        if is_gouging:
            risk_components.append(0.20)
            blacklist_flags.append("Fahiş fiyat")

        if not seller_data.get("is_verified", True):
            risk_components.append(0.15)
            blacklist_flags.append("Doğrulanmamış satıcı")

        # ── ADIM 4: Final Risk Skoru ─────────────────────────────────────
        # Risk bileşenlerini doğrusal toplamla [0, 1] aralığına sıkıştır
        raw_risk = sum(risk_components)
        risk_score = min(1.0, raw_risk)
        risk_level = self._classify_risk(risk_score)

        # ── ADIM 5: Kara Liste Kontrolü (DB hazır olunca) ────────────────
        # if self.db.is_blacklisted(seller_id):
        #     blacklist_flags.append("Kara listede kayıtlı")
        #     risk_score = min(1.0, risk_score + 0.40)
        #     risk_level = "critical"

        self._log_step(
            "Denetim tamamlandı",
            f"risk={risk_score:.3f} ({risk_level}), bayraklar={len(blacklist_flags)}"
        )

        return SecurityAudit(
            product_id=product_id,
            seller_id=seller_id,
            platform=platform,
            has_ssl=seller_data.get("has_ssl", True),
            domain_age_days=seller_data.get("domain_age_days", 999),
            complaint_ratio=complaint_ratio,
            price_anomaly_score=round(price_anomaly_score, 3),
            is_price_dumping=is_dumping,
            is_price_gouging=is_gouging,
            risk_score=round(risk_score, 3),
            risk_level=risk_level,
            blacklist_flags=blacklist_flags,
        )

    # ── Yardımcı Metodlar ────────────────────────────────────────────────

    def _verify_seller(self, seller_id: str, platform: str) -> dict:
        # 🔥 YENİ: URL Temizliği (Hatalı sorguları önlemek için)
        # Boşlukları sil, küçük harfe çevir ve mükerrer .com yazılarını temizle
        clean_platform = str(platform).lower().replace(" ", "").replace(".com", "")
        # Türkçe karakterleri İngilizceye çevir (Basit bir çözüm)
        tr_map = str.maketrans("çğışıöü", "cgisiou")
        clean_platform = clean_platform.translate(tr_map)
        
        clean_seller = str(seller_id).lower().replace(" ", "").replace(".com", "")

        raw = mock_verify_seller(seller_id=clean_seller, platform=clean_platform)

        result = json.loads(raw)
        sellers = result.get("product_data", [{}])
        return sellers[0] if sellers else {}

    def _compute_price_anomaly_score(self, price: float, market_avg: float) -> float:
        """Fiyatın piyasa ortalamasından sapmasını normalize anomali skoruna çevirir."""
        if market_avg == 0:
            return 0.0
        deviation = abs(price - market_avg) / market_avg
        # %0 sapma → 0.0, %80+ sapma → 1.0
        return min(1.0, deviation / 0.8)

    def _classify_risk(self, risk_score: float) -> str:
        for (low, high), level in self.RISK_LEVELS.items():
            if low <= risk_score < high:
                return level
        return "critical"


# ===========================================================================
# §8 — ORKESTRATÖR (Ana Yönetici)
# ===========================================================================

class MarketAnalysisOrchestrator:
    """
    Ajan Orkestratörü — Sistemin Beyin Merkezi

    Yürütme Sırası:
        1. Consultant → TechnicalSpec
        2. Scout      → Ham Veri
        3. Auditor    → SecurityAudit (her ürün için)
        4. Economist  → MarketAnalysis (her ürün için)
        5. Critic     → ReviewAnalysis (risk ile güncellenerek)
        6. Orchestrator → FinalReport (Trust Score sıralaması ile)

    Ajan Bağımlılık Grafiği:
        Consultant ──→ Scout ──→ Auditor ──→ Economist ──→ Critic
                                     ↑                         |
                                     └─────────────────────────┘
                                     (Critic trust_score → Auditor risk_factor ile beslenir)
    """

    TRUST_SCORE_THRESHOLDS = {
        "recommend": 3.5,    # Bu puanın üstü → tavsiye et
        "warn": 2.5,         # Bu aralık → dikkatli ol
        "blacklist": 2.0,    # Bu puanın altı → kara listeye al
    }

    def __init__(self):
        self.consultant = ConsultantAgent()
        self.scout = ScoutAgent()
        self.critic = CriticAgent()
        self.economist = EconomistAgent()
        self.auditor = AuditorAgent()
        logger.info("MarketAnalysisOrchestrator başlatıldı — 5 ajan aktif")

    def run(self, user_query: str, status_callback=None) -> dict:
        """
        Kullanıcı sorgusundan nihai rapora tam yürütme zinciri.
        Metin raporu döndürür.
        """
        logger.info(f"{'='*60}")
        logger.info(f"YENİ ANALİZ BAŞLADI: {user_query[:80]}")
        logger.info(f"{'='*60}")

        # ── AŞAMA 1: Consultant ─────────────────────────────────────────
        if status_callback: status_callback("🔍 Consultant: İhtiyaçlarınız analiz ediliyor (Gemini AI)...")
        spec = self.consultant.analyze(user_query)

        # ── AŞAMA 2: Scout ──────────────────────────────────────────────
        if status_callback: status_callback(f"🛰️ Scout: '{spec.category}' kategorisinde ürünler aranıyor...")
        raw_data = self.scout.gather(spec)
        products = raw_data["products"]
        all_reviews = raw_data["reviews"]
        price_histories = raw_data["price_histories"]

        if not products:
            return {"status": "error", "message": "Ürün bulunamadı."}
            #return "⚠️  Ürün bulunamadı. Lütfen sorgunuzu genişletin."
        
        if status_callback: status_callback(f"✅ {len(products)} ürün bulundu. Denetimler başlıyor...")

        # ── AŞAMA 3-5: Her ürün için Auditor + Economist + Critic ────────
        all_prices = [p["price"] for p in products]
        market_avg = statistics.mean(all_prices) if all_prices else 3000.0

        enriched_products = []
        blacklisted = []

        for product in products:
            pid = product["id"]

            # Auditor → güvenlik denetimi
            audit: SecurityAudit = self.auditor.audit(product, market_avg)

            # Economist → piyasa analizi
            market: MarketAnalysis = self.economist.analyze(
                product=product,
                price_history=price_histories.get(pid, []),
                all_products=products,
                category=spec.category,
            )

            # Critic → yorum analizi (önce 0 risk ile, sonra güncel risk ile)
            reviews = all_reviews.get(pid, [])
            review: ReviewAnalysis = self.critic.analyze(
                product_id=pid,
                reviews=reviews,
                category=spec.category,
                risk_factor=0.0,  # İlk geçiş
            )
            # Auditor risk skoru ile trust_score'u güncelle
            review = self.critic.update_trust_score_with_risk(review, audit.risk_score)

            # Kara liste kararı
            if audit.risk_level == "critical" or review.trust_score < self.TRUST_SCORE_THRESHOLDS["blacklist"]:
                blacklisted.append({
                    "product": product,
                    "reason": audit.blacklist_flags or ["Düşük güven skoru"],
                    "risk_level": audit.risk_level,
                })
                continue  # Kara listeye alınanları sıralamaya dahil etme

            enriched_products.append({
                "product": product,
                "spec": spec,
                "audit": audit,
                "market": market,
                "review": review,
                "trust_score": review.trust_score,
            })

        # ── AŞAMA 6: Trust Score'a Göre Sırala ──────────────────────────
        enriched_products.sort(key=lambda x: x["trust_score"], reverse=True)

        # ── AŞAMA 7: Final Rapor Objesini Oluştur ─────────────────────────
        report_obj = self._build_final_report(
            query=user_query,
            spec=spec,
            ranked_products=enriched_products,
            blacklisted=blacklisted,
            market_avg=market_avg,
        )

        # Artık sadece _format_report (metin) değil, tüm ham veriyi dönüyoruz.
        return {
            "metadata": {
                "query": report_obj.query,
                "category": report_obj.spec.category,
                "budget": {"min": report_obj.spec.budget_min, "max": report_obj.spec.budget_max},
                "use_case": report_obj.spec.primary_use_case,
                "overall_confidence": report_obj.overall_confidence
            },
            "market_summary": {
                "status_text": report_obj.market_status_block,
                "average_price": market_avg
            },
            "top_choice": self._product_to_dict(report_obj.top_recommendation) if report_obj.top_recommendation else None,
            "product_list": [self._product_to_dict(p) for p in report_obj.ranked_products],
            "blacklist": report_obj.blacklist_block,
            "rational_advice": report_obj.rational_advice,
            "raw_text_report": self._format_report(report_obj) # Eski metin raporu yedek olarak dursun
        }
    
    def _product_to_dict(self, entry: dict) -> dict:
        """Yardımcı metod: Ürün objesini sade bir sözlüğe çevirir."""
        p = entry["product"]
        return {
            "name": p["name"],
            "price": p["price"],
            "source": p["source"],
            "url": p["url"],
            "trust_score": entry["trust_score"],
            "risk_level": entry["audit"].risk_level,
            "recommendation": entry["market"].recommendation,
            "price_trend": entry["market"].price_trend
        }

    def _build_final_report(
        self,
        query: str,
        spec: TechnicalSpec,
        ranked_products: list[dict],
        blacklisted: list[dict],
        market_avg: float,
    ) -> FinalReport:
        """Tüm ajan çıktılarını FinalReport'a dönüştürür."""
        top = ranked_products[0] if ranked_products else None

        # Pazar durumu özeti
        if ranked_products:
            market_status = ranked_products[0]["market"].market_status
            market_status_map = {
                "buyer_market": "📉 Alıcı Pazarı — Fiyatlar düşük, müzakere avantajı sizde.",
                "seller_market": "📈 Satıcı Pazarı — Talep yüksek, iyi fiyat bulmak zor.",
                "balanced": "⚖️  Dengeli Pazar — Standart fiyat aralığı geçerli.",
            }
            market_status_block = market_status_map.get(market_status, "Pazar durumu belirsiz.")
        else:
            market_status_block = "⚠️  Yeterli veri yok."

        # Rasyonel tavsiye metni üret
        rational_advice = self._generate_rational_advice(spec, ranked_products, market_avg)

        # Genel güven düzeyi
        trust_scores = [p["trust_score"] for p in ranked_products]
        overall_confidence = statistics.mean(trust_scores) / 5.0 if trust_scores else 0.0

        return FinalReport(
            query=query,
            spec=spec,
            ranked_products=ranked_products,
            top_recommendation=top or {},
            market_status_block=market_status_block,
            blacklist_block=blacklisted,
            rational_advice=rational_advice,
            overall_confidence=round(overall_confidence, 3),
        )

    def _generate_rational_advice(
        self,
        spec: TechnicalSpec,
        ranked: list[dict],
        market_avg: float,
    ) -> str:
        """
        Rasyonel tavsiye metni üretici.
        Tüm ajan sonuçlarını kullanıcının anlayabileceği bir dile çevirir.
        """
        if not ranked:
            return (
                "Bütçe ve spesifikasyonlarınıza uygun güvenilir ürün bulunamadı. "
                "Bütçenizi genişletmeyi veya beklenti listesini kısaltmayı düşünebilirsiniz."
            )

        top = ranked[0]
        product = top["product"]
        market: MarketAnalysis = top["market"]
        review: ReviewAnalysis = top["review"]
        audit: SecurityAudit = top["audit"]

        advice_parts = []

        # Fiyat pozisyonu yorumu
        if market.is_fair_price:
            advice_parts.append(
                f"'{product['name']}' piyasa ortalamasına ({market.market_avg_price:.0f}₺) göre adil fiyatlıdır."
            )
        elif market.price_percentile < 0.3:
            advice_parts.append(
                f"Bu ürün piyasanın en uygun fiyatlı segmentindedir "
                f"({market.price_percentile:.0%} dilimi)."
            )
        
        # Bütçe Kontrolü
        if product['price'] > spec.budget_max:
            diff = product['price'] - spec.budget_max
            advice_parts.append(f"⚠️ NOT: Bu ürün bütçenizi {diff:.0f}₺ aşıyor ancak segmentindeki en rasyonel seçenek bu.")

        # Zamanlama tavsiyesi
        timing_map = {
            "buy_now": "Şu an için iyi bir satın alma fırsatıdır.",
            "wait": f"Fiyat trendi '{market.price_trend}' yönünde; beklemek avantajlı olabilir.",
            "avoid": "Yüksek fiyat oynaklığı nedeniyle bu dönemde satın almak önerilmez.",
        }
        advice_parts.append(timing_map.get(market.recommendation, ""))

        # Risk uyarısı
        if audit.risk_level in ("high", "critical"):
            advice_parts.append(
                f"⚠️ DİKKAT: Bu satıcı/platform için {audit.risk_level.upper()} risk tespit edildi. "
                f"Bayraklar: {', '.join(audit.blacklist_flags[:2])}."
            )

        # Güven skoru yorumu
        trust = top["trust_score"]
        if trust >= 4.0:
            trust_comment = "Güven skoru yüksek, güvenle tercih edilebilir."
        elif trust >= 3.0:
            trust_comment = "Orta düzey güven skoru; alternatiflerle karşılaştırın."
        else:
            trust_comment = "Düşük güven skoru; dikkatli olunması önerilir."
        advice_parts.append(trust_comment)

        return " ".join(filter(None, advice_parts))

    def _format_report(self, report: FinalReport) -> str:
        """FinalReport'u okunabilir terminal çıktısına dönüştürür."""
        lines = []

        lines.append("  AJAN DESTEKLİ DİNAMİK PAZAR ANALİZ RAPORU")

        # ── Sorgu Bilgisi ──────────────────────────────────────────────
        lines.append(f"\n📌 SORGU   : {report.query}")
        lines.append(f"📦 KATEGORİ: {report.spec.category.upper()}")
        lines.append(f"💰 BÜTÇE   : {report.spec.budget_min:.0f}₺ – {report.spec.budget_max:.0f}₺")
        lines.append(f"🎯 KULLANIM: {report.spec.primary_use_case}")

        # ── Pazar Durumu ───────────────────────────────────────────────
        lines.append("\n📊 PAZAR DURUMU")
        lines.append(f"   {report.market_status_block}")
        lines.append(f"   Sistem Güven Düzeyi: {report.overall_confidence:.1%}")

        # ── En İyi Tavsiye ─────────────────────────────────────────────
        if report.top_recommendation:
            top = report.top_recommendation
            p = top["product"]
            m: MarketAnalysis = top["market"]
            r: ReviewAnalysis = top["review"]
            a: SecurityAudit = top["audit"]

            lines.append(f"\n🏆 EN İYİ TAVSİYE")
            lines.append(f"   Ürün      : {p['name']}")
            lines.append(f"   Platform  : {p['source']}")
            lines.append(f"   Fiyat     : {p['price']:.2f}₺")
            lines.append(f"   Güven Skoru: {top['trust_score']:.2f}/5.00")
            lines.append(f"   Risk      : {a.risk_level.upper()}")
            lines.append(f"   Trend     : {m.price_trend}")
            lines.append(f"   Öneri     : {m.recommendation.replace('_', ' ').upper()}")

        # ── Rasyonel Tavsiye ───────────────────────────────────────────
        lines.append("\n🧠 RASYONELl TAVSİYE")
        for sentence in report.rational_advice.split(". "):
            if sentence:
                lines.append(f"   • {sentence.strip()}.")

        # ── Tüm Sıralanmış Ürünler ─────────────────────────────────────
        if report.ranked_products:
            lines.append(f"\n📋 SIRALANMIŞ ÜRÜNLER (Trust Score'a göre)")
            for i, entry in enumerate(report.ranked_products[:5], 1):
                p = entry["product"]
                trust = entry["trust_score"]
                risk = entry["audit"].risk_level
                rec = entry["market"].recommendation
                lines.append(
                    f"   {i}. {p['name'][:35]:<35} "
                    f"| TS={trust:.2f} "
                    f"| {p['price']:.0f}₺ "
                    f"| Risk={risk:<8} "
                    f"| {rec}"
                )

        # ── Kara Liste ─────────────────────────────────────────────────
        if report.blacklist_block:
            lines.append(f"\n🚫 KARA LİSTE ({len(report.blacklist_block)} kayıt)")
            for item in report.blacklist_block:
                p = item["product"]
                reasons = ", ".join(item["reason"][:2])
                lines.append(f"   ✗ {p['name'][:40]} → {reasons}")
        else:
            lines.append("\n✅ Kara listeye alınan ürün/satıcı bulunmamaktadır.")

        return "\n".join(lines)


# ===========================================================================
# §9 — DOĞRUDAN TEST (Terminal Modu)
# ===========================================================================

if __name__ == "__main__":
    print("\n[agents.py — Doğrudan Test Modu]")
    print("Mock araçlar kullanılıyor. LLM bağlantısı devre dışı.\n")

    test_queries = [
        "3000 TL altında oyun için laptop arıyorum, taşınabilir olsun",
        "İş için hafif ve uzun pil ömürlü 5000 TL altı notebook",
        "Öğrenciye uygun uygun fiyatlı telefon",
    ]

    orchestrator = MarketAnalysisOrchestrator()

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'#'*60}")
        print(f"# TEST {i}: {query}")
        print(f"{'#'*60}")
        result = orchestrator.run(query)
        print(result)

def run_analysis(query, status_callback=None):
    """
    Üye 3'ün (app.py) beklediği ana giriş kapısı
    Artık statik veriler değil, orkestratörden gelen gerçek analiz sonuçlarını döner.
    """
    orchestrator = MarketAnalysisOrchestrator()
    
    # 1. GERÇEK ANALİZİ ÇALIŞTIR
    # Bu metod artık bir string değil, zengin bir dictionary (sözlük) döndürüyor.
    analysis_results = orchestrator.run(query, status_callback=status_callback) 
    
    # 2. ÜYE 3 İÇİN VERİYİ PAKETLE
    # app.py'nin mevcut yapısını bozmamak için eski anahtarları (keys) koruyoruz 
    # ama içlerini gerçek verilerle dolduruyoruz.
    final_report = {
        "status": "success",
        "data": analysis_results, # Üye 3'ün gelişmiş arayüzü için tüm ham veri
        
        # Aşağıdakiler app.py'deki mevcut kutucukların çalışmaya devam etmesi için:
        "recommendation": analysis_results["top_choice"]["name"] if analysis_results["top_choice"] else "Uygun ürün bulunamadı",
        "trust_score": int(analysis_results["metadata"]["overall_confidence"] * 100),
        "price": f"{analysis_results['top_choice']['price']:.2f} ₺" if analysis_results["top_choice"] else "N/A",
        "platform": analysis_results["top_choice"]["source"] if analysis_results["top_choice"] else "N/A",
        "verdict": analysis_results["raw_text_report"], # O meşhur ASCII raporu hala burada, isteyen okur
        "warning": analysis_results["rational_advice"][:100] + "..." # Özet bir uyarı metni
    }
    
    return final_report