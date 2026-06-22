# database.py son güncelleme 17.20

import sqlite3
from datetime import datetime

DB_NAME = "market_memory.db"

def get_connection():
    """Veritabanı bağlantısı döndürür."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Sonuçları dict gibi kullanmak için
    return conn

def initialize_database():
    """Tabloları oluşturur. Program ilk açıldığında çağrılır."""
    conn = get_connection()
    cursor = conn.cursor()

    # Arama geçmişi tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SearchHistory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query       TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            result_summary TEXT
        )
    """)

    # Fiyat geçmişi tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS PriceHistory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            price        REAL NOT NULL,
            platform     TEXT,
            timestamp    TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Veritabanı hazır.")

def save_search(query: str, result_summary: str = ""):
    """Kullanıcının aramasını kaydeder."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO SearchHistory (query, timestamp, result_summary) VALUES (?, ?, ?)",
        (query, datetime.now().isoformat(), result_summary)
    )
    conn.commit()
    conn.close()

def save_price(product_name: str, price: float, platform: str = ""):
    """Ürün fiyatını kaydeder."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO PriceHistory (product_name, price, platform, timestamp) VALUES (?, ?, ?, ?)",
        (product_name, price, platform, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_price_history(product_name: str):
    """Bir ürünün fiyat geçmişini getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM PriceHistory WHERE product_name LIKE ? ORDER BY timestamp DESC",
        (f"%{product_name}%",)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_last_search(query: str):
    """Bu ürün daha önce arandı mı? kontrol eder."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM SearchHistory WHERE query LIKE ? ORDER BY timestamp DESC LIMIT 1",
        (f"%{query}%",)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_latest_price(product_name: str) -> float | None:
    """Economist ajanı için en son kaydedilen fiyatı döndürür."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT price FROM PriceHistory 
           WHERE product_name LIKE ? 
           ORDER BY timestamp DESC LIMIT 1""",
        (f"%{product_name}%",)
    )
    row = cursor.fetchone()
    conn.close()
    return row["price"] if row else None

# Test için
if __name__ == "__main__":
    initialize_database()
    save_search("gaming kulaklık", "Test arama")
    save_price("Sony WH-1000XM5", 4299.0, "Trendyol")
    print(get_price_history("Sony"))
    