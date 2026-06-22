# main.py

from database import initialize_database, save_search, save_price, get_last_search

# Arkadaşların modülleri hazır olunca bu satırlar aktif edilecek
try:
    from agents import run_analysis
    AGENTS_READY = True
except Exception as e:
    print(f"❌ AGENTS IMPORT HATASI: {e}")
    AGENTS_READY = False

try:
    from tools import get_product_data
    TOOLS_READY = True
except Exception as e:
    print(f"❌ TOOLS IMPORT HATASI: {e}")
    TOOLS_READY = False

def get_mock_result(query: str) -> dict:
    """Yedek veri."""
    return {
        "recommendation": "Sony WH-1000XM5",
        "trust_score": 87,
        "price": 4299.0,
        "platform": "Trendyol",
        "verdict": "AL - Son 3 ayın en düşük fiyatı",
        "warning": None,
        "source": "mock"
    }

def orchestrate(user_query: str, status_callback=None) -> dict:
    """
    Ana akış:
    1. Girdi al
    2. DB'de geçmiş var mı kontrol et
    3. Ajanları çalıştır (hazırsa) ya da mock döndür
    4. Sonucu kaydet ve döndür
    """
    """Ana akışı yöneten fonksiyon."""

    # Canlı log gönderimi (UI için)
    if status_callback:
        status_callback(f"🔍 Sorgu işleniyor: {user_query}")

    last = get_last_search(user_query)
    if last:
        msg = f"📂 Daha önce arandı: {last['timestamp']}"
        print(msg)
        if status_callback: status_callback(msg)

    if AGENTS_READY:
        if status_callback: status_callback("🤖 Gerçek ajanlar devrede... Analiz başlıyor.")
        
        # 2. KRİTİK: run_analysis fonksiyonuna da bu callback'i gönderiyoruz
        # Not: agents.py içindeki run_analysis fonksiyonunu da güncellemen gerekecek!
        result = run_analysis(user_query, status_callback=status_callback) 
    else:
        if status_callback: status_callback("🧪 Sistem hazırlık aşamasında, mock veri çekiliyor...")
        result = get_mock_result(user_query)


    """
    print(f"\n🔍 Sorgu: {user_query}")

    last = get_last_search(user_query)
    if last:
        print(f"📂 Daha önce arandı: {last['timestamp']}")

    #if AGENTS_READY and TOOLS_READY:
    if AGENTS_READY:
        print("🤖 Gerçek ajanlar devrede...")
        result = run_analysis(user_query) # agents.py'den geliyor
    else:
        print("🧪 Mock veri kullanılıyor...")
        result = get_mock_result(user_query)
    """

    # Veritabanı kayıtları
    save_search(user_query, result.get("recommendation", ""))
    save_price(
        result.get("recommendation", ""), 
        result.get("price", 0), 
        result.get("platform", "")
    )

    return result


if __name__ == "__main__":
    initialize_database()
    sonuc = orchestrate("gaming kulaklık")
    for k, v in sonuc.items():
        print(f"  {k}: {v}")