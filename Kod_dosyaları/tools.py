"""
Kurulum:
    pip install selenium webdriver-manager youtube-transcript-api python-whois requests beautifulsoup4 google-search-results
"""
# ===========================================================================
# BÖLGE 1: Tüm kütüphaneler
# ===========================================================================
import json, random, re, time, ssl, socket
from datetime import datetime, timedelta
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field  
import os
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# Artık anahtarları sistemden çekiyoruz
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SERPAPI_KEY  = os.getenv("SERPAPI_KEY")

# ─────────────────────────────────────────────
# BAĞIMLILIK KONTROLLERİ
# ─────────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
    print("[OK] Selenium hazır.")
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[UYARI] Selenium kurulu değil.")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YOUTUBE_API_AVAILABLE = True
    print("[OK] YouTube Transcript API hazır.")
except ImportError:
    YOUTUBE_API_AVAILABLE = False
    print("[UYARI] youtube-transcript-api kurulu değil.")

try:
    import whois
    WHOIS_AVAILABLE = True
    print("[OK] python-whois hazır.")
except ImportError:
    WHOIS_AVAILABLE = False
    print("[UYARI] python-whois kurulu değil.")

try:
    import requests
    REQUESTS_AVAILABLE = True
    print("[OK] requests hazır.")
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[UYARI] requests kurulu değil.")

try:
    from serpapi import GoogleSearch
    SERPAPI_AVAILABLE = True
    print("[OK] SerpAPI hazır.")
except ImportError:
    SERPAPI_AVAILABLE = False
    print("[UYARI] google-search-results kurulu değil.")

# ===========================================================================
# BÖLGE 2: ÜYE 2 - GERÇEK ARAÇLAR (Arkadaşının yazdığı motorlar)
# ===========================================================================

# Geçersiz ürün adı filtreleri
GECERSIZ_AD_BASLANGIC = [
    "teslimat", "delivery", "kargo", "reklam", "sponsored",
    "ücretsiz", "hızlı", "kampanya"
]

# SerpAPI'den gelmesin istenen kaynaklar (Selenium ile zaten çekiyoruz)
SERPAPI_ENGEL_KAYNAKLAR = ["amazon"]

# ═══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def _get_driver():
    """Headless Chrome driver döndürür."""
    if not SELENIUM_AVAILABLE:
        return None
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        print(f"[HATA] Chrome driver başlatılamadı: {e}")
        return None


def _gecerli_ad_mi(ad: str) -> bool:
    """Ürün adının geçerli olup olmadığını kontrol eder."""
    if not ad or len(ad) < 5:
        return False
    ad_kucuk = ad.lower().strip()
    for filtre in GECERSIZ_AD_BASLANGIC:
        if ad_kucuk.startswith(filtre):
            return False
    return True

# ═══════════════════════════════════════════════════════════════════
# YARDIMCI: YEDEK VERİ
# ═══════════════════════════════════════════════════════════════════

def _mock_urun_verisi(urun_adi: str, kaynak: str, adet: int) -> list:
    """Gerçek veri alınamadığında yedek veri döndürür."""
    markalar = ["Samsung", "Apple", "Xiaomi", "Sony", "LG", "Huawei", "Logitech", "JBL", "Bose", "Philips"]
    isimler = ["Pro", "Lite", "Plus", "Max", "Ultra", "Mini"]
    baz = random.uniform(500, 15000)
    return [
        {
            "kaynak": kaynak,
            "urun_adi": f"{random.choice(markalar)} {urun_adi} {isimler[i % len(isimler)]}",
            "fiyat": round(baz * random.uniform(0.85, 1.20), 2),
            "marka": random.choice(markalar),
            "yorum_sayisi": random.randint(50, 2000),
            "puan": round(random.uniform(3.5, 4.9), 1),
            "url": f"https://www.{kaynak}.com/urun/{urun_adi.replace(' ', '-')}-{i+1}"
        }
        for i in range(adet)
    ]

# ═══════════════════════════════════════════════════════════════════
# ARAÇ 1B: AMAZON TR SCRAPER (Selenium)
# ═══════════════════════════════════════════════════════════════════

def scrape_amazon(urun_adi: str, max_sonuc: int = 5) -> list:
    print(f"[Amazon] '{urun_adi}' aranıyor...")

    if SELENIUM_AVAILABLE:
        driver = _get_driver()
        if driver:
            try:
                driver.get(f"https://www.amazon.com.tr/s?k={urun_adi.replace(' ', '+')}")
                time.sleep(5)
                driver.execute_script("window.scrollTo(0, 1000)")
                time.sleep(3)

                urunler = []
                kartlar = driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
                print(f"[Amazon] {len(kartlar)} kart bulundu.")

                for kart in kartlar[:max_sonuc * 2]:
                    try:
                        ad = kart.find_element(By.CSS_SELECTOR, "h2 span").text.strip()

                        if not _gecerli_ad_mi(ad):
                            continue

                        fiyat = 0.0
                        try:
                            fiyat_text = kart.find_element(
                                By.CSS_SELECTOR, "span.a-price span.a-offscreen"
                            ).get_attribute("innerHTML").strip()
                            fiyat_text = fiyat_text.replace("&nbsp;", "").replace("TL", "").replace(".", "").replace(",", ".").strip()
                            fiyat = float(re.sub(r'[^\d.]', '', fiyat_text))
                        except Exception:
                            pass

                        url = ""
                        try:
                            url = kart.find_element(By.CSS_SELECTOR, "a.a-link-normal").get_attribute("href")
                            if url and not url.startswith("http"):
                                url = f"https://www.amazon.com.tr{url}"
                        except Exception:
                            pass

                        puan = 0.0
                        try:
                            puan_text = kart.find_element(By.CSS_SELECTOR, "span.a-icon-alt").get_attribute("innerHTML")
                            puan = float(puan_text.split()[0].replace(",", "."))
                        except Exception:
                            pass

                        yorum = 0
                        try:
                            yorum_text = kart.find_element(By.CSS_SELECTOR, "span.a-size-base").text
                            yorum = int(re.sub(r'\D', '', yorum_text))
                        except Exception:
                            pass

                        if ad and fiyat > 0:
                            urunler.append({
                                "kaynak": "amazon",
                                "urun_adi": ad[:100],
                                "fiyat": fiyat,
                                "marka": ad.split()[0],
                                "yorum_sayisi": yorum,
                                "puan": puan,
                                "url": url
                            })

                        if len(urunler) >= max_sonuc:
                            break

                    except Exception:
                        continue

                driver.quit()

                if urunler:
                    print(f"[Amazon] ✅ {len(urunler)} ürün bulundu.")
                    return urunler

                print("[Amazon] Veri parse edilemedi.")

            except Exception as e:
                print(f"[Amazon HATA] {e}")
                try:
                    driver.quit()
                except Exception:
                    pass

    print("[Amazon] Yedek veri kullanılıyor.")
    return _mock_urun_verisi(urun_adi, "amazon", max_sonuc)


# ═══════════════════════════════════════════════════════════════════
# ARAÇ 1C: TRENDYOL + DİĞER SİTELER (SerpAPI)
# ═══════════════════════════════════════════════════════════════════

def scrape_with_serpapi(urun_adi: str, max_sonuc: int = 5) -> list:
    """
    SerpAPI Google Shopping ile Trendyol, N11, Vatan, MediaMarkt gibi
    sitelerden ürün çeker. Hepsiburada ve Amazon filtrelenir.
    """
    print(f"\n[SerpAPI] '{urun_adi}' aranıyor...")

    if not SERPAPI_AVAILABLE:
        print("[SerpAPI] Kütüphane kurulu değil.")
        return _mock_urun_verisi(urun_adi, "trendyol", max_sonuc)

    if not SERPAPI_KEY or SERPAPI_KEY == "BURAYA_SERPAPI_KEY":
        print("[SerpAPI] API key girilmemiş.")
        return _mock_urun_verisi(urun_adi, "trendyol", max_sonuc)

    try:
        params = {
            "engine": "google_shopping",
            "q": urun_adi,
            "hl": "tr",
            "gl": "tr",
            "api_key": SERPAPI_KEY
        }

        arama = GoogleSearch(params)
        sonuclar = arama.get_dict()

        if "error" in sonuclar:
            print(f"[SerpAPI HATASI] {sonuclar['error']}")
            

        urun_listesi = sonuclar.get("shopping_results", [])

        if not urun_listesi:
            print("[SerpAPI] shopping_results boş geldi.")
            

        urunler = []

        for item in urun_listesi[:max_sonuc * 3]:
            try:
                ad = item.get("title", "").strip()
                if not _gecerli_ad_mi(ad):
                    continue

                kaynak = item.get("source", "diger")

                # Hepsiburada ve Amazon'u SerpAPI'den engelle
                if any(s in kaynak.lower() for s in SERPAPI_ENGEL_KAYNAKLAR):
                    continue

                # Fiyat
                fiyat = item.get("extracted_price")
                if fiyat is None:
                    fiyat_text = str(item.get("price", ""))
                    fiyat_text = (
                        fiyat_text
                        .replace("TL", "").replace("₺", "")
                        .replace(".", "").replace(",", ".")
                        .strip()
                    )
                    fiyat_text = re.sub(r"[^\d.]", "", fiyat_text)
                    fiyat = float(fiyat_text) if fiyat_text else 0.0

                # Puan
                puan_text = str(item.get("rating", "0")).replace(",", ".")
                try:
                    puan = float(puan_text)
                except Exception:
                    puan = 0.0

                # Yorum
                yorum_sayisi = item.get("reviews", 0)
                try:
                    yorum_sayisi = int(str(yorum_sayisi).replace(".", ""))
                except Exception:
                    yorum_sayisi = 0

                # URL
                url = item.get("product_link") or item.get("link") or ""

                urunler.append({
                    "kaynak": kaynak,
                    "urun_adi": ad[:120],
                    "fiyat": fiyat,
                    "marka": ad.split()[0] if ad else "Bilinmiyor",
                    "yorum_sayisi": yorum_sayisi,
                    "puan": puan,
                    "url": url
                })

                if len(urunler) >= max_sonuc:
                    break

            except Exception as e:
                print(f"[SerpAPI ÜRÜN HATASI] {e}")
                continue

        if urunler:
            print(f"[SerpAPI] ✅ {len(urunler)} ürün bulundu.")
            return urunler

        print("[SerpAPI] Veri parse edilemedi.")
    

    except Exception as e:
        print(f"[SerpAPI GENEL HATA] {e}")
    

# ═══════════════════════════════════════════════════════════════════
# ANA ENTEGRASYON FONKSİYONU — 1. Üye sadece bunu çağırır
# ═══════════════════════════════════════════════════════════════════

def get_product_data(urun_adi: str) -> dict:
    """
    Tüm kaynaklardan veri toplar ve birleşik JSON döndürür.
    1. Üye sadece bu fonksiyonu çağırır, içine karışmaz.

    Döndürür:
    {
        "status": "success",
        "urun_adi": str,
        "sonuclar": [...],
        "fiyat_aralik": { "min", "max", "ortalama" },
        "zaman_damgasi": str
    }
    """

    # tools.py içindeki ilgili kısmı bu mantıkla güncelle:
    amazon_sonuc = scrape_amazon(urun_adi, max_sonuc=3) or [] # None gelirse boş liste yap
    serp_sonuc   = scrape_with_serpapi(urun_adi, max_sonuc=4) or [] # None gelirse boş liste yap

    tum_sonuclar = amazon_sonuc + serp_sonuc
    
    fiyatlar = [u["fiyat"] for u in tum_sonuclar if u["fiyat"] and u["fiyat"] > 0]

    return {
        "status": "success",
        "urun_adi": urun_adi,
        "sonuclar": tum_sonuclar,
        "fiyat_aralik": {
            "min": min(fiyatlar) if fiyatlar else 0,
            "max": max(fiyatlar) if fiyatlar else 0,
            "ortalama": round(sum(fiyatlar) / len(fiyatlar), 2) if fiyatlar else 0
        },
        "zaman_damgasi": datetime.now().isoformat()
    }

# ═══════════════════════════════════════════════════════════════════
# ARAÇ 2: YOUTUBE TRANSCRIPT
# ═══════════════════════════════════════════════════════════════════

def get_youtube_transcript(video_url: str, max_karakter: int = 3000) -> dict:
    """YouTube video URL'inden transcript çeker. Video indirilmez."""
    video_id = None
    for pattern in [r"(?:v=)([a-zA-Z0-9_-]{11})", r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})"]:
        eslesme = re.search(pattern, video_url)
        if eslesme:
            video_id = eslesme.group(1)
            break

    if not video_id:
        return {"status": "hata", "mesaj": "Geçersiz YouTube URL.", "transcript": ""}

    print(f"[YouTube] Video ID: {video_id} için transcript çekiliyor...")

    if YOUTUBE_API_AVAILABLE:
        try:
            ytt = YouTubeTranscriptApi()
            for dil in [["tr"], ["en"], None]:
                try:
                    transkript = ytt.fetch(video_id, languages=dil) if dil else ytt.fetch(video_id)
                    tam_metin = " ".join([
                        bolum.text if hasattr(bolum, 'text') else bolum.get("text", "")
                        for bolum in transkript
                    ])
                    print(f"[YouTube] ✅ Transcript çekildi ({len(tam_metin)} karakter).")
                    return {
                        "status": "success",
                        "video_id": video_id,
                        "transcript": tam_metin[:max_karakter],
                        "uzunluk_karakter": len(tam_metin),
                        "not": "Kısaltıldı." if len(tam_metin) > max_karakter else ""
                    }
                except Exception:
                    continue
        except Exception as e:
            print(f"[YouTube HATA] {e}")

    return {
        "status": "mock",
        "video_id": video_id,
        "transcript": (
            "İnceleme videosunda ürün genel olarak olumlu değerlendirilmiştir. "
            "Ses kalitesi ve mikrofon performansı öne çıkan özellikler olarak belirtilmiştir. "
            "Fiyat/performans açısından kategorisinde iyi bir seçenek olarak önerilmektedir."
        ),
        "uzunluk_karakter": 200,
        "not": "Yedek veri."
    }

# ═══════════════════════════════════════════════════════════════════
# ARAÇ 3: FRAUD DETECTOR
# ═══════════════════════════════════════════════════════════════════

def check_seller_fraud_risk(site_url: str, urun_fiyati: float, piyasa_ortalamasi: float) -> dict:
    """Satıcı güven kontrolü — SSL, domain yaşı, fiyat sapması."""
    print(f"[Fraud Detector] '{site_url}' kontrol ediliyor...")

    domain = re.sub(r"https?://(www\.)?", "", site_url).split("/")[0]
    uyarilar = []
    risk_puanlari = []

    ssl_gecerli = False
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            ssl_gecerli = True
            risk_puanlari.append(-10)
    except Exception:
        uyarilar.append("SSL sertifikası geçersiz.")
        risk_puanlari.append(40)

    domain_yasi_gun = None
    if WHOIS_AVAILABLE:
        try:
            w = whois.whois(domain)
            creation = w.creation_date
            if isinstance(creation, list):
                creation = creation[0]
            if creation:
                domain_yasi_gun = (datetime.now() - creation).days
                if domain_yasi_gun < 180:
                    uyarilar.append(f"Domain çok yeni ({domain_yasi_gun} gün)!")
                    risk_puanlari.append(35)
                elif domain_yasi_gun < 365:
                    risk_puanlari.append(15)
        except Exception:
            uyarilar.append("Domain yaşı alınamadı.")
            risk_puanlari.append(20)

    if domain_yasi_gun is None:
        guvenilir = ["trendyol.com", "hepsiburada.com", "amazon.com.tr", "n11.com", "vatan.com", "mediamarkt.com.tr"]
        domain_yasi_gun = 3650 if any(s in domain for s in guvenilir) else 500

    fiyat_sapma = 0.0
    if piyasa_ortalamasi > 0 and urun_fiyati > 0:
        fiyat_sapma = ((piyasa_ortalamasi - urun_fiyati) / piyasa_ortalamasi) * 100
        if fiyat_sapma > 40:
            uyarilar.append(f"⚠️ Fiyat piyasadan %{fiyat_sapma:.1f} düşük — dolandırıcılık riski!")
            risk_puanlari.append(50)
        elif fiyat_sapma > 25:
            uyarilar.append(f"Fiyat piyasadan %{fiyat_sapma:.1f} düşük — şüpheli.")
            risk_puanlari.append(25)

    risk_skoru = min(100, max(0, sum(risk_puanlari)))
    risk_seviyesi = "DÜŞÜK" if risk_skoru < 20 else ("ORTA" if risk_skoru < 50 else "YÜKSEK")

    if not uyarilar:
        uyarilar.append("✅ Risk faktörü tespit edilmedi.")

    print(f"[Fraud Detector] Risk: {risk_seviyesi} ({risk_skoru}/100)")
    return {
        "status": "success",
        "site": domain,
        "ssl_gecerli": ssl_gecerli,
        "domain_yasi_gun": domain_yasi_gun,
        "fiyat_sapma_yuzdesi": round(fiyat_sapma, 2),
        "risk_skoru": risk_skoru,
        "risk_seviyesi": risk_seviyesi,
        "uyarilar": uyarilar
    }

# ═══════════════════════════════════════════════════════════════════
# ARAÇ 4: HABER ARAMA (NewsAPI)
# ═══════════════════════════════════════════════════════════════════

def search_product_news(urun_adi: str, max_haber: int = 5) -> dict:
    """NewsAPI ile güncel haberler çeker."""
    print(f"[Haber] '{urun_adi}' için haberler aranıyor...")

    if REQUESTS_AVAILABLE:
        try:
            for dil in ["tr", "en"]:
                yanit = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": urun_adi,
                        "language": dil,
                        "sortBy": "publishedAt",
                        "pageSize": max_haber,
                        "apiKey": NEWS_API_KEY
                    },
                    timeout=10
                )
                data = yanit.json()
                if data.get("status") == "ok" and data.get("articles"):
                    haberler = []
                    yeni_model = False
                    indirim = False

                    for m in data["articles"]:
                        baslik = m.get("title", "") or ""
                        b = baslik.lower()
                        if any(k in b for k in ["yeni model", "lansman", "release", "launch"]):
                            yeni_model = True
                        if any(k in b for k in ["indirim", "kampanya", "sale", "discount"]):
                            indirim = True
                        haberler.append({
                            "baslik": baslik,
                            "kaynak": m.get("source", {}).get("name", ""),
                            "tarih": (m.get("publishedAt") or "")[:10],
                            "ozet": m.get("description") or "",
                            "url": m.get("url") or ""
                        })

                    print(f"[Haber] ✅ {len(haberler)} haber bulundu.")
                    return {
                        "status": "success",
                        "urun_adi": urun_adi,
                        "haberler": haberler,
                        "yeni_model_uyarisi": yeni_model,
                        "indirim_uyarisi": indirim
                    }
        except Exception as e:
            print(f"[Haber HATA] {e}")

    return {
        "status": "mock",
        "urun_adi": urun_adi,
        "haberler": [
            {
                "baslik": f"{urun_adi} — güncel inceleme",
                "kaynak": "Technopat",
                "tarih": datetime.now().strftime("%Y-%m-%d"),
                "ozet": f"{urun_adi} kategorisinde öne çıkan modeller.",
                "url": "https://technopat.net"
            }
        ],
        "yeni_model_uyarisi": False,
        "indirim_uyarisi": False
    }

# ===========================================================================
# ÜYE 1 (AJANLAR) İÇİN GEREKLİ TÜM KÖPRÜLER VE MOCK İSİMLERİ
# ===========================================================================
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# 1. Giriş Şemaları
class ProductSearchInput(BaseModel):
    query: str = Field(description="Ürün adı veya kategori")

class ReviewScraperInput(BaseModel):
    product_id: str = Field(description="Ürün ID veya sorgusu")

# 2. GERÇEK MOTOR BAĞLANTILARI
def mock_search_products(query: str, **kwargs) -> str:
    """Ajan 'search' dediğinde arkadaşının gerçek motorunu çalıştırır."""
    data = get_product_data(query) 
    return json.dumps(data, ensure_ascii=False)

def mock_scrape_reviews(product_id: str, **kwargs):
    """Ajan 'review' dediğinde YouTube veya diğer yorumları çeker."""
    # Arkadaşının youtube fonksiyonu varsa onu çağıralım
    try:
        return json.dumps(get_youtube_transcript(product_id), ensure_ascii=False)
    except:
        return json.dumps({"status": "success", "transcript": "Yorum verisi çekilemedi."})

def mock_verify_seller(seller_id: str, platform: str = "amazon"):
    """Dolandırıcılık dedektifini çalıştırır."""
    fraud = check_seller_fraud_risk(f"https://www.{platform}.com", 1000, 1500)
    return json.dumps(fraud, ensure_ascii=False)

def mock_get_price_history(product_id: str, days: int = 30):
    """Fiyat geçmişi (Şimdilik boş dönebilir, database.py üzerinden işlenecek)"""
    return json.dumps({"status": "success", "product_data": []})

# 3. LANCHCAIN ARAÇ PAKETLERİ
search_products_tool = StructuredTool.from_function(
    func=mock_search_products,
    name="search_products",
    description="E-ticaret sitelerinden gerçek veri çeker.",
    args_schema=ProductSearchInput,
)

scrape_reviews_tool = StructuredTool.from_function(
    func=mock_scrape_reviews,
    name="scrape_reviews",
    description="Ürün yorumlarını ve videolarını analiz eder.",
    args_schema=ReviewScraperInput,
)

# 2. Ajanın çağıracağı köprü fonksiyonu
def search_products(query: str) -> str:
    """Ajan 'ara' dediğinde arkadaşının gerçek get_product_data fonksiyonunu çalıştırır."""
    data = get_product_data(query) 
    return json.dumps(data, ensure_ascii=False)

# 3. LangChain Araç Tanımları (Ajanların göreceği nesneler)
search_products_tool = StructuredTool.from_function(
    func=search_products,
    name="search_products",
    description="E-ticaret sitelerinden gerçek zamanlı veri çeker.",
    args_schema=ProductSearchInput,
)

# 4. AGENTS.PY'NİN İSTEDİĞİ O MEŞHUR LİSTELER
ALL_TOOLS = [search_products_tool, scrape_reviews_tool]
TOOL_MAP = {tool.name: tool for tool in ALL_TOOLS}

# ═══════════════════════════════════════════════════════════════════
# TEST BLOĞU
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TOOLS.PY FINAL TEST")
    print("=" * 60)
 
    print
    print(json.dumps(get_product_data("laptop"), ensure_ascii=False, indent=2))
 
    print("\n" + "=" * 60)
    print("✅ TOOLS.PY FINAL TEST TAMAMLANDI!")
    print("=" * 60)