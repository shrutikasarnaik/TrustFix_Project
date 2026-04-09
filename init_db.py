# Temporary Quick Fix for 'area' column
with db.get_db_connection() as conn:
    try:
        conn.execute("ALTER TABLE Users ADD COLUMN area TEXT")
        conn.commit()
        print("✅ Added 'area' column successfully!")
    except:
        pass