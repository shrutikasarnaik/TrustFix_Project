import sqlite3

conn = sqlite3.connect('trustfix.db')
cursor = conn.execute("PRAGMA table_info(Users)")
print("--- ACTUAL COLUMNS IN USERS TABLE ---")
for info in cursor.fetchall():
    print(f"Column Name: {info[1]} | Type: {info[2]}")
conn.close()