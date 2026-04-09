import sqlite3

# Connect to your project database file
conn = sqlite3.connect('database.db') # Make sure this matches your app.py filename
cursor = conn.cursor()

# Create the Owners table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Owners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_name TEXT NOT NULL,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password TEXT NOT NULL
    )
''')

conn.commit()
conn.close()
print("Table 'Owners' created successfully!")