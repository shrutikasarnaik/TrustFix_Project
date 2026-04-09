import sqlite3

def fix():
    # Make sure this name matches your actual db file name (e.g., database.db)
    conn = sqlite3.connect('database.db') 
    cursor = conn.cursor()
    
    # Create the missing notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Table created successfully!")

if __name__ == "__main__":
    fix()