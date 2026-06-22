# app.py - Agentic Shopping Analyst [FULL VERSION]
import streamlit as st
import pandas as pd
from database import initialize_database, get_price_history, save_search, get_connection
import datetime

# --- 1. GLOBAL KONFİGÜRASYON ---
st.set_page_config(
    page_title="Agentic Shopping Analyst", 
    page_icon="🕵️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Veritabanını her başlangıçta kontrol et
initialize_database()

# --- 2. SENIOR UI/UX CSS DOKUNUŞLARI ---
# --- 2. SENIOR UI/UX CSS DOKUNUŞLARI ---
# --- 2. SENIOR UI/UX CSS DOKUNUŞLARI ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    /* 1. GLOBAL STANDARTLAR */
    .stApp, .stMarkdown, p, label, li {
        font-family: 'Inter', sans-serif !important;
    }

    /* 2. GENİŞLİK VE HİZALAMA (Arama Barı & Loglar Eşitlendi) */
    /* st.status, st.warning ve arama barı sütununu %80 genişliğe sabitledik */
    div[data-testid="stStatus"], .stAlert, div[data-testid="column"] > div[data-testid="stVerticalBlock"] {
        max-width: 85% !important;
        margin: 0 auto !important;
    }
            
    /* 3. ARAMA BARI VE BUTON (KESİN SENKRONİZASYON) */
    
    /* Arama Barı Konteynırı */
    div[data-testid="stTextInput"] > div {
        height: 60px !important; /* Sabit pixel yüksekliği en güvenlisidir */
        background-color: #262730 !important;
        border: 1px solid #444 !important;
        border-radius: 10px !important;
    }

    /* Arama Barı Yazı Alanı */
    div[data-testid="stTextInput"] input {
        height: 60px !important;
        font-size: 1.3rem !important;
        background-color: transparent !important;
        line-height: 60px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    /* Buton Konteynırı (Hizalama Sorununun Kaynağı) */
    div[data-testid="stButton"] {
        margin-top: 0 !important; /* Streamlit'in hayalet etiket boşluğunu öldür */
        height: 60px !important;
    }

    /* Butonun Kendisi */
    div[data-testid="stButton"] button {
        height: 60px !important;
        width: 100% !important;
        font-size: 1.3rem !important;
        border-radius: 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: #ff4b4b !important;
        border: none !important;
    }
            
    /* Press Enter kutusunun renk farkını ve kendisini tamamen yok eder */
    div[data-testid="InputInstructions"] {
        background-color: #262730 !important; /* Arka plan rengini sildik */
        border: none !important;
        box-shadow: none !important;              /* Gölge varsa temizledik */
    }
            
    /* 4. METRİK KARTLARI */
    div[data-testid="stMetric"] {
        background-color: #1e2130 !important;
        border: 1px solid #31333f !important;
        padding: 25px !important;
        border-radius: 15px !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 2.4rem !important;
        font-weight: 800 !important;
        color: #ff4b4b !important;
    }
            
    .box-header {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        color: #ff4b4b !important;
        margin-bottom: 15px !important;
    }

    /* Rasyonel analiz kutusunu içeriğe göre daraltan ve boşluğu bitiren kural */
    .rational-box {
        background-color: #1e2130;
        padding: 25px;
        border-radius: 15px;
        border-right: 8px solid #ff4b4b;
        border-top: 1px solid #333;
        min-height: 350px !important; /* Boşluğu bitirmek için yüksekliği azalttık */
        height: auto !important;
    }

    /* Alternatif kartlarındaki başlık ve fiyat puntolarını büyütme */
    .alt-card-title {
        font-size: 1.35rem !important; /* 🥈 kart başlıkları büyütüldü */
        font-weight: 600;
        color: #fff;
    }
    .alt-card-price {
        font-size: 1.5rem !important; /* 🥈 fiyatlar büyütüldü */
        color: #ff4b4b;
        font-weight: 800;
    }
            
    table { 
        width: 100%; 
        border-collapse: collapse; 
    }
    th { 
        font-size: 1.3rem !important; 
        color: #60b4ff !important; /* Başlıklar kırmızı kalsın */
        text-align: left !important;
        padding: 15px !important;
        border-bottom: 2px solid #31333f !important;
    }
    td { 
        font-size: 1.25rem !important; 
        padding: 15px !important;
        border-bottom: 1px solid #31333f !important;
        color: #eee !important; /* Hücre yazıları açık gri/beyaz */
    }

    /* Linklerin normal ve üzerine gelme durumları */
    table a {
        transition: 0.3s;
    }
    table a:hover {
        color: #90d5ff !important; /* Sadece üzerine gelince kırmızı olsun */
        text-decoration: underline !important;
    }

    </style>
    """, unsafe_allow_html=True)

# --- 3. BAŞLIK VE GİRİŞ ---
st.markdown("<h1 style='text-align: center; font-size: 3.8rem; margin-bottom: 0;'>🕵️ Ajan Destekli Alışveriş Asistanı</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.3rem; color: #888;'>Çoklu ajan sistemiyle pazar istihbaratı ve rasyonel analiz.</p>", unsafe_allow_html=True)
st.write("##")

# --- 4. ARAMA MOTORU ALANI ---
with st.container():
    # Kenarlardan 1'er birim boşluk bırakıp ortadaki 3 birimi kullanıyoruz
    _, col_mid, _ = st.columns([0.15, 0.7, 0.15])
    with col_mid:
        col_search, col_btn = st.columns([5, 1])
        with col_search:
            user_query = st.text_input("Ürün Ara", placeholder="Hangi ürünü analiz etmemi istersiniz?", label_visibility="collapsed")
        with col_btn:
            search_button = st.button("Analiz Et", use_container_width=True, type="primary")

# --- 5. ANA ANALİZ DÖNGÜSÜ ---
if search_button and user_query:
    from main import orchestrate
    save_search(user_query)

    # Ajanların durumunu gösteren interaktif box
    with st.status("🔍 Ajanlar pazar taraması yapıyor...", expanded=True) as status:
        log_area = st.empty()
        log_lines = []

        def live_callback(msg: str):
            # ISO zaman damgalarını daha okunabilir formata çeviren minör dokunuş
            if "Daha önce arandı:" in msg:
                try:
                    # ISO formatındaki kısmı ayıkla ve formatla
                    parts = msg.split(": ")
                    dt_part = parts[1].strip()
                    # Sadece tarihi ve saati al (Örn: 13/05/2026 11:29)
                    clean_dt = datetime.datetime.fromisoformat(dt_part).strftime('%d/%m/%Y %H:%M')
                    msg = f"{parts[0]}: {clean_dt}"
                except:
                    pass
            log_lines.append(msg)
            log_area.markdown("\n\n".join(log_lines))

        result = orchestrate(user_query, status_callback=live_callback)
        status.update(label="✅ Analiz Tamamlandı!", state="complete", expanded=False)

    # Sonuçları ekrana bas
    if result.get("status") == "success":
        data = result.get("data", {})
        top = data.get("top_choice") or {}
        product_list = data.get("product_list", [])
        
        # ── METRİK PANELİ ──
        st.write("##")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ortalama Fiyat", f"{data['market_summary'].get('average_price', 0):,.0f} ₺")
        m2.metric("Pazar Durumu", data['market_summary'].get("status_text", "Dengeli").split("—")[0])
        m3.metric("Sistem Güveni", f"%{int(data['metadata'].get('overall_confidence', 0)*100)}")
        m4.metric("Ürün Havuzu", f"{len(product_list)} Ürün")

        st.divider()

        # --- 🟢 TÜRKÇELEŞTİRME MANTIKLARI ---
        trend_map = {"stable": "SABİT", "upward": "YUKARI", "downward": "AŞAĞI", "volatile": "DEĞİŞKEN"}
        risk_map = {"low": "DÜŞÜK", "medium": "ORTA", "high": "YÜKSEK"}
    
        t_trend = trend_map.get(top.get("price_trend", "").lower(), top.get("price_trend", "BELİRSİZ"))
        t_risk = risk_map.get(top.get("risk_level", "").lower(), top.get("risk_level", "BELİRSİZ"))

        # ── ANA ANALİZ (Hero & Rational) ──
        col_hero, col_rat = st.columns([1.6, 1])

        with col_hero:
            #st.markdown("### 🏆 Stratejik Seçim")
            with st.container():
                price = top.get("price", 0)

                st.markdown(f"""
                    <div style="background-color: #1e2130; padding: 25px; border-radius: 15px; border-left: 8px solid #ff4b4b; border-top: 1px solid #333; min-height: 380px; display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div class="box-header">🏆 Stratejik Seçim</div>
                            <h1 style="margin: 10px 0; font-size: 2.1rem; color: #fff; line-height: 1.2;">{top.get('name', '—')}</h1>
                            <p style="font-size: 1.2rem; color: #aaa;">En yüksek güven skoru ve pazar uyumluluğuna sahip ürün.</p>
                        </div>
                        <div>
                            <hr style="border: 0.1px solid #333; margin: 20px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size:1.3rem;">🏪 <b>Platform:</b> {top.get('source', '—').upper()}</span>
                                <span style="color: #ff4b4b; font-weight: bold; font-size: 1.8rem;">💰 {price:,.0f} ₺</span>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        with col_rat:
            st.markdown(f"""
                <div class="rational-box">
                    <div class="box-header">🧠 Rasyonel Analiz</div>
                    <div style="color: #eee; font-size: 1.2rem; line-height: 1.8; margin-top: 10px;">
                        {"".join([f"<div style='margin-bottom:10px;'>✅ {s.strip()}.</div>" for s in data.get('rational_advice', '').split('. ') if s])}
                    </div>
                </div>
            """, unsafe_allow_html=True)

            rational_text = data.get("rational_advice", "Analiz verisi işlenemedi.")

        # ── 🏆 EK ANALİZ KARTI (Analizden Hemen Sonra) ──
        st.write("##")
        c1, c2, c3 = st.columns(3)
        c1.info(f"⭐ **Puan:** {top.get('trust_score', 0):.2f} / 5.0")
        c2.success(f"📈 **Trend:** {t_trend}")
        c3.warning(f"🛡️ **Risk Seviyesi:** {t_risk}")
    
        st.link_button("🚀 SATIN ALMA SAYFASINA GİT", top.get("url", "#"), use_container_width=True)

        # ── TABLO VE GRAFİK BÖLÜMÜ ──
        st.divider()
        tab_list, tab_graph = st.tabs(["📋 Tüm Alternatifler", "📉 Fiyat Projeksiyonu"])


        with tab_list:
            if product_list:
                df = pd.DataFrame(product_list)
                
                # --- VERİ TÜRKÇELEŞTİRME VE TEMİZLİK ---
                risk_map = {"low": "🟢 Düşük", "medium": "🟡 Orta", "high": "🔴 Yüksek"}
                rec_map = {"buy_now": "✅ Hemen Al", "wait": "⏳ Bekle", "avoid": "❌ Kaçın"}
                
                df["risk_level"] = df["risk_level"].map(lambda x: risk_map.get(x.lower(), x))
                df["recommendation"] = df["recommendation"].map(lambda x: rec_map.get(x.lower(), x))

                # --- 🥈 & 🥉 SEÇENEKLER (Podyum Paneli) ---
                if len(df) > 1:
                    st.markdown("#### 🥈 Diğer Güçlü Alternatifler")
                    alt_cols = st.columns(min(len(df)-1, 2))

                    for i, col in enumerate(alt_cols):
                        # Top choice zaten Hero'da, o yüzden 1. ve 2. indexleri alıyoruz
                        item = df.iloc[i+1] 
                        with col:
                            # İsimleri akıllıca kısaltan ve kutuyu tıklanabilir kılan yapı
                            st.markdown(f"""
                            <div style="background-color: #1e2130; padding: 20px; border-radius: 15px; border: 1px solid #333; min-height: 250px; display: flex; flex-direction: column; justify-content: space-between;">
                                <div>
                                    <div class="alt-card-title">{item['name'][:45]}...</div>
                                    <div class="alt-card-price">{item['price']:,.0f} ₺</div>
                                    <small style="color: #888;">🏪 {item['source'].upper()} | ⭐ {item['trust_score']:.2f}</small>
                                </div>
                                <div style="margin-top: 15px;">
                                    <a href="{item.get('url', '#')}" target="_blank" style="text-decoration: none;">
                                        <div style="background-color: #31333f; color: white; text-align: center; padding: 12px; border-radius: 8px; font-weight: 600; border: 1px solid #444;">
                                            Ürünü İncele 🚀
                                        </div>
                                    </a>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    st.write("##")

                # --- GELİŞMİŞ VE ETKİLEŞİMLİ VERİ TABLOSU ---
                st.markdown("#### 📊 Pazar Analiz Listesi")
        
                if product_list:
                    # 1. Veriyi hazırla (URL sütununu da dahil etmeyi unutma)
                    display_df = df[["name", "price", "source", "trust_score", "risk_level", "recommendation", "url"]].copy()
            
                    # 2. Ürün isimlerini HTML Link etiketine dönüştür
                    display_df["name"] = display_df.apply(
                        lambda x: f'<a href="{x["url"]}" target="_blank" style="color: #eee; text-decoration: none; font-weight: 600;">{x["name"]}</a>', 
                        axis=1
                    )
            
                    # 3. Diğer görsel hazırlıklar (Skor ve Fiyat)
                    display_df["trust_score"] = display_df["trust_score"].apply(lambda x: "🟢" * int(x) + "⚪" * (5 - int(x)) + f" ({x:.2f})")
                    display_df["price"] = display_df["price"].apply(lambda x: f"{x:,.0f} ₺")
            
                    # 4. Gereksizleşen URL sütununu tablodan çıkar ve başlıkları Türkçeleştir
                    display_df = display_df.drop(columns=["url"])
                    display_df.columns = ["Ürün Adı", "Fiyat", "Platform", "Güven Skoru", "Risk Durumu", "Ajan Kararı"]
            
                    # 5. HTML olarak bas (escape=False linklerin çalışmasını sağlar)
                    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

        with tab_graph:
            # Gerçek fiyat geçmişini DB'den çek
            history = get_price_history(top.get("name", "")) if top else []
            
            if history:
                df_h = pd.DataFrame(history)
                df_h["timestamp"] = pd.to_datetime(df_h["timestamp"]).dt.strftime("%d/%m %H:%M")
                st.area_chart(df_h.set_index("timestamp")["price"])
            else:
                # Mock veri (Eğer DB henüz boşsa görsel doluluk için)
                st.info("Bu ürün için henüz yeterli tarihsel veri toplanmadı. Tahmini trend aşağıdadır.")
                mock_data = pd.DataFrame({
                    "Tarih": ["3 Ay Önce", "2 Ay Önce", "1 Ay Önce", "Bugün"],
                    "Fiyat": [price*1.15, price*1.10, price*1.05, price]
                })
                st.line_chart(mock_data.set_index("Tarih"))

    else:
        st.error("Analiz sırasında bir hata oluştu. Lütfen sorgunuzu değiştirip tekrar deneyin.")

# --- 6. KARŞILAMA EKRANI (Arama yokken) ---
elif not user_query:
    st.write("##")
    c_a, c_b, c_c = st.columns(3)
    c_a.info("🔍 **Geniş Tarama:** Ajanlar Amazon ve Google veri tabanlarını anlık sorgular.")
    c_b.success("🛡️ **Güvenlik:** SSL sertifikaları ve satıcı geçmişleri Auditor tarafından denetlenir.")
    c_c.warning("📊 **Ekonomik Karar:** Economist ajanı fiyatın adilliğini piyasa ortalamasına göre ölçer.")

# --- 7. SIDEBAR (GEÇMİŞ) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1162/1162456.png", width=100)
    st.title("Asistan Paneli")
    st.divider()
    
    with st.expander("🕓 Son Aramalarım", expanded=True):
        try:
            conn = get_connection()
            df_history = pd.read_sql("SELECT query, timestamp FROM SearchHistory ORDER BY timestamp DESC LIMIT 8", conn)
            conn.close()
            for _, row in df_history.iterrows():
                st.caption(f"📅 {row['timestamp'][5:16]} | {row['query']}")
        except:
            st.write("Arama geçmişi boş.")