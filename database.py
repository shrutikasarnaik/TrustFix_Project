import sqlite3
import random

def get_db_connection():
    conn = sqlite3.connect('database.db')  
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # Create Owners Table first
    conn.execute('''CREATE TABLE IF NOT EXISTS Owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    password TEXT NOT NULL)''')

    # FIXED: Single buildings table matching your HTML fields
    conn.execute('''CREATE TABLE IF NOT EXISTS buildings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    society_name TEXT NOT NULL,
                    house_no TEXT,
                    landmark TEXT,
                    city TEXT,
                    state TEXT,
                    pincode TEXT,
                    FOREIGN KEY (owner_id) REFERENCES Owners(id))''')

    # 2. USERS TABLE
    conn.execute('''CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    name TEXT NOT NULL, 
                    role TEXT NOT NULL, 
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    owner_id INTEGER, 
                    area TEXT,  -- <--- ADD THIS LINE HERE
                    email TEXT, phone TEXT, aadhar_no TEXT, profile_pic TEXT,
                    occupation TEXT, family_members INTEGER, prev_address TEXT, 
                    rent_start TEXT, rent_end TEXT, emergency_contact TEXT,
                    work_type TEXT, experience TEXT, availability TEXT, 
                    service_rate TEXT, reference TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES Owners (id))''')

    # 3. TICKETS TABLE
    conn.execute('''CREATE TABLE IF NOT EXISTS tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id TEXT UNIQUE,
                        user_id INTEGER,
                        technician_id INTEGER,
                        issue_type TEXT,
                        urgency TEXT,
                        description TEXT,
                        photo TEXT,
                        status TEXT DEFAULT 'Pending',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES Users (id))''')

    # 4. PROPERTIES & MESSAGES
    conn.execute('''CREATE TABLE IF NOT EXISTS Properties (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id INTEGER NOT NULL,
                        society_name TEXT NOT NULL,
                        address TEXT NOT NULL,
                        FOREIGN KEY (owner_id) REFERENCES Owners (id))''')

    conn.execute('''CREATE TABLE IF NOT EXISTS Messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL,
                        sender_type TEXT NOT NULL,
                        receiver_id INTEGER NOT NULL,
                        receiver_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    conn.commit()
    conn.close()
    
def fix_existing_database():
    conn = get_db_connection()
    # List of ALL columns we need to ensure exist
    columns_to_add = [
        ("tickets", "user_id", "INTEGER"),
        ("tickets", "photo", "TEXT"),
        ("tickets", "created_at", "DATETIME"), # THE FIX
        ("Users", "occupation", "TEXT"),
        ("Users", "family_members", "INTEGER"),
        ("Users", "emergency_contact", "TEXT")
    ]
    
    for table, column, dtype in columns_to_add:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {dtype}")
            print(f"Verified/Added {column} to {table}")
        except sqlite3.OperationalError:
            # This means column already exists, which is fine!
            pass
            
    conn.commit()
    conn.close()
    print("Database Surgery Complete. Your data is safe.")



def save_direct_message(s_id, s_type, r_id, r_type, content):
    conn = get_db_connection()
    conn.execute('''INSERT INTO Messages (sender_id, sender_type, receiver_id, receiver_type, message) 
                    VALUES (?, ?, ?, ?, ?)''', (s_id, s_type, r_id, r_type, content))
    conn.commit()
    conn.close()
    

# INSIDE database.py
def save_owner_portfolio(data, societies, cities, states, pincodes, landmarks):
    conn = get_db_connection()
    try:
        # Insert Owner
        cursor = conn.execute('''INSERT INTO Owners (full_name, username, email, phone, password) 
                                VALUES (?, ?, ?, ?, ?)''', 
                             (data['owner_name'], data['username'], data['email'], data['phone'], data['password']))
        owner_id = cursor.lastrowid
        
        # Insert Buildings linked to this Owner
        for i in range(len(societies)):
            conn.execute('''INSERT INTO buildings (owner_id, society_name, city, state, pincode, landmark) 
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (owner_id, societies[i], cities[i], states[i], pincodes[i], landmarks[i]))
        
        conn.commit()
        return owner_id # Return the ID for the session
    except Exception as e:
        print(f"Database Error: {e}")
        return None
    finally:
        conn.close()

# YOUR ORIGINAL FUNCTIONS (UNCHANGED)
def add_ticket(user_id, issue_type, urgency, description, photo_name=None):
    conn = get_db_connection()
    # We use TIC- (3 letters) to match your frontend links
    t_id = f"TIC-{random.randint(1000, 9999)}"
    
    conn.execute('''INSERT INTO tickets (ticket_id, user_id, issue_type, urgency, description, photo, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                 (t_id, user_id, issue_type, urgency, description, photo_name, 'Pending'))
    conn.commit()
    conn.close()
    return t_id

def get_user_tickets(username):
    conn = get_db_connection()
    tickets = conn.execute('SELECT * FROM tickets WHERE username = ?', (username,)).fetchall()
    conn.close()
    return tickets

def get_chat_contacts(user_id):
    conn = get_db_connection()
    query = "SELECT DISTINCT u.id, u.name, u.role FROM Users u JOIN tickets t ON (u.id = t.technician_id OR u.id = t.tenant_id) WHERE (t.tenant_id = ? OR t.technician_id = ?) AND u.id != ?"
    rows = conn.execute(query, (user_id, user_id, user_id)).fetchall()
    conn.close()
    return rows

def get_messages(sender_id, receiver_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM Messages WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?) ORDER BY timestamp ASC",
                        (sender_id, receiver_id, receiver_id, sender_id)).fetchall()
    conn.close()
    return rows

def check_owner_login(username, password):
    conn = get_db_connection()
    # We check if both username and password match a row in Owners
    owner = conn.execute('SELECT * FROM Owners WHERE username = ? AND password = ?', 
                         (username, password)).fetchone()
    conn.close()
    return owner # Returns the row if found, else None

def save_direct_message(s_id, s_type, r_id, r_type, content):
    conn = get_db_connection()
    # Ensure the query matches the 5 arguments
    conn.execute('''INSERT INTO Messages 
                    (sender_id, sender_type, receiver_id, receiver_type, message) 
                    VALUES (?, ?, ?, ?, ?)''', 
                 (s_id, s_type, r_id, r_type, content))
    conn.commit()
    conn.close()

# Add these columns to your Users table in database.py
# If the table exists, run these ALTER commands or reset the DB
def upgrade_users_table():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE Users ADD COLUMN email TEXT")
        conn.execute("ALTER TABLE Users ADD COLUMN phone TEXT")
        conn.execute("ALTER TABLE Users ADD COLUMN aadhar_no TEXT")
        conn.execute("ALTER TABLE Users ADD COLUMN profile_pic TEXT")
        conn.commit()
    except:
        pass # Columns already exist
    conn.close()

def delete_ticket_from_db(t_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tickets WHERE ticket_id = ?', (t_id,))
    conn.commit()
    conn.close()

def fix_created_at_error():
    conn = get_db_connection()
    try:
        # Specifically adding the column the Dashboard is crying about
        conn.execute("ALTER TABLE tickets ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        conn.commit()
        print("Successfully added created_at column!")
    except sqlite3.OperationalError:
        print("Column created_at already exists or another error occurred.")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    # Force add the missing column
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE tickets ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        conn.commit()
        print("✅ Success: created_at column added!")
    except:
        print("ℹ️ Note: created_at already exists or another error occurred.")
    conn.close()