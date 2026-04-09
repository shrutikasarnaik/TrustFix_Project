import sqlite3

def reset_table():
    conn = sqlite3.connect('trustfix.db')
    try:
        # This deletes the broken 3-column table
        conn.execute("DROP TABLE IF EXISTS Users")
        conn.commit()
        print("✅ Broken 'Users' table deleted.")
        print("Now, run 'python app.py' to recreate it correctly.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

reset_table()