# agent-based-market-analyser
An AI agent-based dynamic market analysis and decision support system developed using Python and Streamlit.
# 🕵️ Ajan Destekli Alışveriş Asistanı

> Sakarya Üniversitesi Bilgisayar Mühendisliği  
> Yapay Zeka / Sistem Tasarımı Projesi

Agentic Shopping Analyst, çoklu ajan mimarisi (*Multi-Agent System*) kullanarak kullanıcılar için otonom pazar araştırması ve rasyonel satın alma analizi gerçekleştiren yapay zeka tabanlı bir asistandır.

---

# 🎯 Proje Hakkında

Bu proje, karmaşık e-ticaret verilerini anlamlandırmak ve kullanıcıya en güvenilir satın alma tavsiyesini sunmak amacıyla geliştirilmiştir.

Sistem yalnızca fiyat odaklı çalışmaz; güvenlik, kullanıcı deneyimi ve piyasa trendlerini harmanlayan bir *Trust Score (Güven Endeksi)* algoritması üzerine kuruludur.

---

# 🛠️ Kullanılan Teknolojiler

## Backend / Yapay Zeka

- Python
- CrewAI
- LangChain

## LLM Entegrasyonları

- Google Gemini Pro
- Groq (Llama-3)

## Frontend

- Streamlit
- Custom Glassmorphism UI

## Veri Araçları

- Selenium
- SerpAPI (Google Shopping)
- YouTube Transcript API

## Güvenlik & Veri

- SQLite3
- WHOIS
- SSL Checker

---

# ✨ Özellikler

## 🏗️ Ajan Mimarisi (Sequential Reasoning)

Sistem, birbirine veri aktaran 5 temel ajan üzerinden çalışır:

### 👨‍💼 Consultant
Doğal dil isteğini teknik spesifikasyonlara dönüştürür.

### 🔎 Scout
Amazon ve Google Shopping üzerinden canlı pazar taraması yapar.

### 🛡️ Auditor
SSL sertifikası, domain yaşı ve fiyat anomalileri ile risk analizi yapar.

### 📈 Economist
Fiyat trendlerini analiz ederek *"Al / Bekle"* stratejisi belirler.

### 💬 Critic
Kullanıcı yorumlarındaki negatiflik yanlılığını (bias) temizleyerek gerçek memnuniyeti ölçer.

---

# 🧠 Karar Mekanizması: Trust Score

Sistemin rasyonel karar verme süreci aşağıdaki matematiksel model üzerine kuruludur:

math
Trust Score = \frac{(0.6 \cdot ExpertScore) + (0.4 \cdot UserScore)}{1.0 + RiskFactor}


---

# ✅ Sistem Yetenekleri

- Otonom muhakeme ve ajanlar arası ardışık akıl yürütme
- Canlı veri normalizasyonu
- Siber güvenlik denetimi
- Veri odaklı modern dashboard arayüzü

---

# 📊 Sistem Modeli

Sistem 6 ana bileşenden oluşur:

| Bileşen | Açıklama |
|---|---|
| Orchestrator | Ajanları yöneten ana kontrol birimi |
| Data Scrapers | Web kazıma ve API servisleri |
| Sentiment Engine | NLP tabanlı duygu analizi motoru |
| Security Validator | Domain ve sertifika doğrulama modülü |
| Logic Controller | Trust Score hesaplama mantığı |
| UI Layer | Streamlit tabanlı sunum katmanı |

---

# 📦 Kurulum

## Gereksinimler

- Python 3.10+
- Google API Key (Gemini)
- Groq API Key
- SerpAPI Key

---

## Kurulum Adımları

### 1️⃣ Projeyi klonlayın

bash
git clone [repo-url]


### 2️⃣ Gerekli kütüphaneleri yükleyin

bash
pip install -r requirements.txt


### 3️⃣ .env dosyasını oluşturun

env
GOOGLE_API_KEY=your_key
GROQ_API_KEY=your_key
SERPAPI_API_KEY=your_key


### 4️⃣ Uygulamayı çalıştırın

bash
streamlit run app.py


---

# 🚀 Proje Durumu

Proje aktif geliştirme aşamasındadır.

Gelecek güncellemelerde aşağıdaki özelliklerin eklenmesi planlanmaktadır:

- 📉 Fiyat takip botları
- 🛒 Daha fazla e-ticaret platformu entegrasyonu
- 🧠 Gelişmiş analiz modülleri
- 📊 Daha kapsamlı veri görselleştirme araçları

---

# ⚠️ Not

Bu proje bir araştırma ve geliştirme projesidir.

---

# 👨‍💻 Geliştirici Bilgisi

*2026 — Sakarya Üniversitesi Bilgisayar Mühendisliği*
