import os
import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
import database as db 
import random

app = Flask(__name__)
app.secret_key = 'trustfix_secure_key_2026'

# Configuration
UPLOAD_FOLDER = 'static/uploads/profiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def run_migrations():
    """Consolidated migration to handle all table updates at once."""
    with db.get_db_connection() as conn:
        # 1. Update Users and Tickets Tables
        required_columns = [
            ("Users", "phone", "TEXT"), ("Users", "email", "TEXT"),
            ("Users", "aadhar_no", "TEXT"), ("Users", "occupation", "TEXT"),
            ("Users", "city", "TEXT"), ("Users", "area", "TEXT"),
            ("Users", "flat_no", "TEXT"), ("Users", "address", "TEXT"),
            ("Users", "prev_address", "TEXT"), ("Users", "emergency_contact", "TEXT"),
            ("Users", "monthly_rent", "INTEGER"), ("Users", "society_id", "INTEGER"),
            ("Users", "work_type", "TEXT"), ("Users", "service_rate", "TEXT"),
            ("Users", "specialty", "TEXT"), ("Users", "profile_pic", "TEXT"),
            ("Users", "created_at", "DATETIME DEFAULT '2026-03-31'"),
            ("tickets", "technician_id", "INTEGER"), ("tickets", "rating", "INTEGER"),
            ("tickets", "feedback", "TEXT")
        ]
        
        for table, col, col_type in required_columns:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            if col not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        
        # 2. Create
        conn.execute('''CREATE TABLE IF NOT EXISTS buildings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            owner_id INTEGER NOT NULL,
                            society_name TEXT NOT NULL,
                            location TEXT NOT NULL,
                            city TEXT,
                            country TEXT,
                            FOREIGN KEY (owner_id) REFERENCES Owners(id))''')

        # 3. Create Messages Table
        conn.execute('''CREATE TABLE IF NOT EXISTS Messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_id INTEGER NOT NULL,
                            sender_type TEXT NOT NULL,
                            receiver_id INTEGER NOT NULL,
                            receiver_type TEXT NOT NULL,
                            message TEXT,
                            image_file TEXT,
                            is_read BOOLEAN DEFAULT 0,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

# Run all setup tasks
run_migrations()
db.init_db()


@app.route('/')
def landing(): 
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form.get('username', '').strip()
        pword = request.form.get('password', '').strip()

        conn = db.get_db_connection()

        # Check Owners Table First
        owner = conn.execute('SELECT * FROM Owners WHERE LOWER(username) = LOWER(?) AND password = ?', 
                             (uname, pword)).fetchone()
        
        if owner:
            session.clear() 
            session['user_id'] = owner['id']
            session['user'] = owner['full_name']
            session['role'] = 'owner' 
            conn.close()
            return redirect(url_for('owner_dash'))

        # Check General Users Table (Tenants/Technicians)
        user = conn.execute('SELECT * FROM Users WHERE LOWER(username) = LOWER(?) AND password = ?', 
                            (uname, pword)).fetchone()
        conn.close()

        if user:
            session.clear()
            session['user_id'] = user['id']
            session['user'] = user['name']
            
            user_role = str(user['role']).strip().lower()
            session['role'] = user_role 

            if user_role == 'technician':
                return redirect(url_for('tech_dashboard'))
            else:
                return redirect(url_for('dashboard'))

        flash("Invalid Credentials. Please try again.", "danger")
            
    return render_template('login.html')

@app.route('/register_owner', methods=['GET', 'POST'])
def register_owner():
    if request.method == 'POST':
        owner_data = {
            'owner_name': request.form.get('owner_name'),
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'password': request.form.get('password')
        }

        societies = request.form.getlist('society_name[]')
        cities = request.form.getlist('city[]')
        states = request.form.getlist('state[]')
        pincodes = request.form.getlist('pincode[]')
        landmarks = request.form.getlist('landmark[]')

        new_owner_id = db.save_owner_portfolio(owner_data, societies, cities, states, pincodes, landmarks)
        
        if new_owner_id:
            session.clear()
            session['user_id'] = new_owner_id
            session['user'] = owner_data['owner_name']
            session['role'] = 'Owner'
            
            flash("Welcome to TrustFix! Your portfolio has been set up.", "success")
            return redirect(url_for('owner_dash'))
        else:
            flash("Username already exists. Please choose another.", "danger")
            return redirect(url_for('register_owner'))
            
    return render_template('owner_signup.html')

@app.route('/owner_dash')
def owner_dash():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = db.get_db_connection()
    owner_id = session['user_id']
    
    try:
        owner_data = conn.execute('SELECT name FROM owners WHERE id = ?', (owner_id,)).fetchone()
        if not owner_data:
            owner_data = conn.execute('SELECT name FROM owner WHERE id = ?', (owner_id,)).fetchone()
    except sqlite3.OperationalError:
        owner_data = conn.execute('SELECT name FROM Users WHERE id = ? AND role = "owner"', (owner_id,)).fetchone()

    owner_name = owner_data['name'] if owner_data else "Owner"

    stats = {'active_tickets': 0, 'buildings': 0, 'total_tenants': 0}
    
    try:

        stats['active_tickets'] = conn.execute('''
            SELECT COUNT(t.id) FROM tickets t 
            JOIN Users u ON t.user_id = u.id 
            WHERE u.owner_id = ? AND t.status = 'Pending'
        ''', (owner_id,)).fetchone()[0]

        stats['total_tenants'] = conn.execute("SELECT COUNT(*) FROM Users WHERE role = 'tenant' AND owner_id = ?", (owner_id,)).fetchone()[0]
        stats['buildings'] = conn.execute("SELECT COUNT(*) FROM buildings WHERE owner_id = ?", (owner_id,)).fetchone()[0]

        # 2. Urgent Dispatch 
        alerts = conn.execute('''
            SELECT t.id, t.ticket_id, t.issue_type as title, t.status, t.description, t.photo,
                   u.name as tenant_name, u.area, u.occupation as flat_no 
            FROM tickets t
            JOIN Users u ON t.user_id = u.id
            WHERE u.owner_id = ? AND t.status = 'Pending'
            ORDER BY t.created_at DESC
        ''', (owner_id,)).fetchall()

        # 3. Notifications
        notifications = []
        for alert in alerts:
            notifications.append({
                'title': 'New Ticket',
                'desc': f"{alert['tenant_name']} has a {alert['title']} issue."
            })

        technicians = conn.execute('SELECT id, name, work_type FROM Users WHERE role = "technician" AND owner_id = ?', (owner_id,)).fetchall()

        trends = conn.execute('''
            SELECT u.area, t.issue_type, COUNT(t.id) as count 
            FROM tickets t JOIN Users u ON t.user_id = u.id
            WHERE u.owner_id = ?
            GROUP BY u.area, t.issue_type ORDER BY count DESC LIMIT 5
        ''', (owner_id,)).fetchall()

    except Exception as e:
        print(f"Dashboard Error: {e}")
        alerts, technicians, trends, notifications = [], [], [], []
    finally:
        conn.close()

    return render_template('owner_dash.html', 
                           owner_name=owner_name, 
                           stats=stats, 
                           alerts=alerts, 
                           technicians=technicians, 
                           trends=trends,
                           notifications=notifications)

@app.route('/tech_dashboard')
def tech_dashboard():
    if 'user_id' not in session or str(session.get('role')).strip().lower() != 'technician':
        return redirect(url_for('login'))
    
    tech_id = session['user_id']
    conn = db.get_db_connection()
    
    user_info = conn.execute('SELECT * FROM Users WHERE id = ?', (tech_id,)).fetchone()
    
    my_tasks = conn.execute('''
        SELECT t.*, u.name as username, u.area FROM tickets t JOIN Users u ON t.user_id = u.id 
        WHERE t.technician_id = ? AND t.status != 'Resolved'
    ''', (tech_id,)).fetchall()
    
    # Generate Notification
    notifications = []
    for task in my_tasks:
        if task['status'] == 'Assigned':
            notifications.append({
                'title': 'Assigned Task',
                'message': f"New task #{task['ticket_id']} needs your attention."
            })
            
    conn.close()
    return render_template('tech_dash.html', user=user_info, tasks=my_tasks, 
                           notifications=notifications, unread_count=len(notifications))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    with db.get_db_connection() as conn:
        user_info = conn.execute('SELECT * FROM Users WHERE id = ?', (user_id,)).fetchone()
        
        user_tickets = conn.execute('''
            SELECT * FROM tickets 
            WHERE user_id = ? 
            ORDER BY id DESC
        ''', (user_id,)).fetchall()
        
        notifications = []
        for ticket in user_tickets:
            if ticket['status'] == 'Assigned':
                notifications.append({
                    'title': 'Technician Assigned',
                    'message': f"Technician assigned to Ticket #{ticket['ticket_id']}",
                })
            elif ticket['status'] == 'Completed':
                notifications.append({
                    'title': 'Task Completed',
                    'message': f"Ticket #{ticket['ticket_id']} marked as Completed.",
                })

    return render_template('tenant_dash.html', 
                           user=user_info, 
                           tickets=user_tickets, 
                           notifications=notifications,
                           unread_count=len(notifications))

@app.route('/assign_technician', methods=['POST'])
def assign_technician():
    ticket_id = request.form.get('ticket_id')
    tech_id = request.form.get('tech_id')
    
    if not tech_id:
        flash("Please select a technician!", "warning")
        return redirect(url_for('owner_dash'))

    try:
        conn = db.get_db_connection()
        conn.execute('''
            UPDATE tickets 
            SET technician_id = ?, status = 'Assigned' 
            WHERE id = ?
        ''', (tech_id, ticket_id))
        conn.commit()
        conn.close()
        flash("Technician assigned! Waiting for their acceptance.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for('owner_dash'))

@app.route('/respond_to_assignment/<int:id>/<string:response>')
def respond_to_assignment(id, response):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    if response == 'accept':
        # Now it is officially "In Progress"
        conn.execute("UPDATE tickets SET status = 'In Progress' WHERE id = ?", (id,))
        flash("Task accepted! Please head to the location.", "success")
    else:
        conn.execute("UPDATE tickets SET technician_id = NULL, status = 'Pending' WHERE id = ?", (id,))
        flash("Task declined. It has been sent back to the Owner.", "info")
    
    conn.commit()
    conn.close()
    return redirect(url_for('tech_dashboard'))

@app.route('/resolve_with_evidence', methods=['POST'])
def resolve_with_evidence():
    ticket_id = request.form.get('ticket_id')
    completion_notes = request.form.get('completion_notes')
    file = request.files.get('completion_photo')
    
    if not file:
        flash("Please upload a photo of the completed work!", "warning")
        return redirect(url_for('tech_dashboard'))

    filename = secure_filename(file.filename)
    # Ensure this path matches your static folder structure
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    conn = db.get_db_connection()
    # Move to Resolved and save the "After" proof
    conn.execute('''
        UPDATE tickets 
        SET status = 'Resolved', 
            completion_photo = ?, 
            completion_notes = ? 
        WHERE id = ?
    ''', (filename, completion_notes, ticket_id))
    conn.commit()
    conn.close()
    
    flash("Job completed! Sent to work history.", "success")
    return redirect(url_for('tech_dashboard'))

@app.route('/view_user_profile/<int:user_id>')
def view_user_profile(user_id):
    current_role = session.get('role')
    if not current_role or current_role.lower() not in ['owner', 'admin']:
        return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    
    conn.execute('CREATE TABLE IF NOT EXISTS tech_assignments (tech_id INTEGER, building_id INTEGER)')
    user = conn.execute('SELECT * FROM Users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        conn.close()
        flash("User not found!", "danger")
        return redirect(url_for('manage_users'))

    # Fetch their history
    history = conn.execute(
        'SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    
    # Fetch multiple societies if the user is a technician
    societies = []
    if user['role'].lower() == 'technician':
        societies = conn.execute('''
            SELECT b.society_name, b.house_no 
            FROM buildings b
            JOIN tech_assignments ta ON b.id = ta.building_id
            WHERE ta.tech_id = ?
        ''', (user_id,)).fetchall()
    
    conn.close()
    
    return render_template('view_user_profile.html', user=user, history=history, societies=societies)

@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    owner_id = session['user_id']
    search_query = request.args.get('search', '').strip()
    
    conn = db.get_db_connection()
    conn.row_factory = sqlite3.Row 
    
    if search_query:
        search_param = f"%{search_query}%"
        filter_sql = "AND (name LIKE ? OR area LIKE ? OR email LIKE ?)"
        params = (owner_id, search_param, search_param, search_param)
    else:
        filter_sql = ""
        params = (owner_id,)

    # Fetch Tenants
    tenants = conn.execute(f'''
        SELECT * FROM Users 
        WHERE (role="Tenant" OR role="tenant") AND owner_id = ? {filter_sql}
    ''', params).fetchall()
                          
    # Fetch Technicians
    technicians = conn.execute(f'''
        SELECT * FROM Users 
        WHERE (role="Technician" OR role="technician") AND owner_id = ? {filter_sql}
    ''', params).fetchall()
    
    conn.close()
    return render_template('manage_users.html', tenants=tenants, technicians=technicians, search_query=search_query)

@app.route('/manage_members')
def manage_members():
    conn = db.get_db_connection()
    members = conn.execute('SELECT * FROM Users WHERE owner_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('manage_members.html', members=members)


@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    owner_id = session.get('user_id')
    if not owner_id:
        return redirect(url_for('login'))

    conn = db.get_db_connection()

    owner_buildings = conn.execute(
        'SELECT id, society_name, house_no, city, state FROM buildings WHERE owner_id = ?', 
        (owner_id,)
    ).fetchall()

    if request.method == 'POST':
        role = request.form.get('role') 
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        
        building_ids = request.form.getlist('building_ids') 
        
        flat_no = request.form.get('flat_no') if role == 'tenant' else None
        specialization = request.form.get('specialization') if role == 'technician' else None

        try:
            primary_b = building_ids[0] if building_ids else None
            
            cursor = conn.execute('''
                INSERT INTO Users (name, username, password, role, owner_id, flat_no, work_type, society_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (full_name, username, password, role, owner_id, flat_no, specialization, primary_b))
            
            new_user_id = cursor.lastrowid

            if role == 'technician' and len(building_ids) > 0:
                conn.execute('''CREATE TABLE IF NOT EXISTS tech_assignments 
                                (tech_id INTEGER, building_id INTEGER)''')
                
                for b_id in building_ids:
                    conn.execute('INSERT INTO tech_assignments (tech_id, building_id) VALUES (?, ?)', 
                                 (new_user_id, b_id))
            
            conn.commit()
            flash(f" Success! {role.capitalize()} assigned to {len(building_ids)} properties.", "success")
            return redirect(url_for('create_user'))
            
        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            flash("Database Error: Username might be taken.", "danger")
        finally:
            conn.close()

    return render_template('create_user.html', owner_buildings=owner_buildings)

@app.route('/inbox')
@app.route('/chat/<receiver_type>/<int:receiver_id>')
def inbox(receiver_type=None, receiver_id=None):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    my_id = session['user_id']
    my_role = session['role']
    my_type = 'Owner' if my_role == 'Owner' else 'User'

    if my_role == 'Owner':
        contacts = conn.execute("""
            SELECT id, name, role, area, 'User' as type 
            FROM Users 
            WHERE owner_id = ?""", (my_id,)).fetchall()
    else:
        contacts = conn.execute("""
            SELECT o.id, o.full_name as name, 'Owner' as role, 'Headquarters' as area, 'Owner' as type 
            FROM Owners o
            JOIN Users u ON u.owner_id = o.id
            WHERE u.id = ?""", (my_id,)).fetchall()

    active_user = None
    messages = []
    if receiver_id and receiver_type:
        if receiver_type == 'Owner':
            active_user = conn.execute("SELECT id, full_name as name, 'Owner' as role, 'HQ' as area FROM Owners WHERE id = ?", (receiver_id,)).fetchone()
        else:
            active_user = conn.execute("SELECT id, name, role, area FROM Users WHERE id = ?", (receiver_id,)).fetchone()

        messages = conn.execute('''
            SELECT * FROM Messages 
            WHERE (sender_id = ? AND sender_type = ? AND receiver_id = ? AND receiver_type = ?)
            OR (sender_id = ? AND sender_type = ? AND receiver_id = ? AND receiver_type = ?)
            ORDER BY timestamp ASC''', 
            (my_id, my_type, receiver_id, receiver_type, receiver_id, receiver_type, my_id, my_type)).fetchall()

    conn.close()
    return render_template('inbox.html', 
                           contacts=contacts, 
                           active_user=active_user, 
                           messages=messages, 
                           receiver_type=receiver_type)



@app.route('/send_message', methods=['POST'])
def send_message():
    receiver_id = request.form.get('receiver_id')
    receiver_type = request.form.get('receiver_type')
    message_text = request.form.get('message')
    image = request.files.get('image')
    
    filename = None
    if image and image.filename != '':
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    my_type = 'Owner' if session.get('role') == 'Owner' else 'User'

    conn = db.get_db_connection()
    try:
        conn.execute('''
            INSERT INTO Messages (sender_id, sender_type, receiver_id, receiver_type, message, image_file)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], my_type, receiver_id, receiver_type, message_text, filename))
        conn.commit()
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        conn.close()

    return redirect(url_for('inbox', receiver_id=receiver_id, receiver_type=receiver_type))

@app.route('/raise_ticket', methods=['GET', 'POST'])
def raise_ticket():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    user_id = session['user_id']
    
    user_info = conn.execute('SELECT * FROM Users WHERE id = ?', (user_id,)).fetchone()

    if request.method == 'POST':
        issue_type = request.form.get('issue_type')
        urgency = request.form.get('urgency')
        description = request.form.get('description')
        file = request.files.get('issue_photo')
        
        photo_name = None
        if file and file.filename != '':
            photo_name = secure_filename(f"ticket_{user_id}_{random.randint(100,999)}.jpg")
            file.save(os.path.join(UPLOAD_FOLDER, photo_name))
        t_id = f"TIC-{random.randint(1000, 9999)}"
        
        conn.execute('''INSERT INTO tickets (ticket_id, user_id, issue_type, urgency, description, photo) 
                        VALUES (?, ?, ?, ?, ?, ?)''', 
                     (t_id, user_id, issue_type, urgency, description, photo_name))
        conn.commit()
        conn.close()
        
        return render_template('ticket_success.html', ticket_id=t_id)

    conn.close()
    return render_template('raise_ticket.html', user=user_info)

@app.route('/delete_message/<int:msg_id>')
def delete_message(msg_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = db.get_db_connection()
    conn.execute('DELETE FROM Messages WHERE id = ? AND sender_id = ?', 
                 (msg_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return redirect(request.referrer)

@app.route('/my_profile', methods=['GET', 'POST'])
def my_profile():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn = db.get_db_connection()
    user_id = session['user_id']

    user_data = conn.execute('SELECT * FROM Users WHERE id = ?', (user_id,)).fetchone()

    if request.method == 'POST':
        data = request.form
        file = request.files.get('profile_pic')
        
        filename = user_data['profile_pic'] 
        if file and file.filename != '':
            filename = secure_filename(f"user_{user_id}.jpg")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        update_query = '''
            UPDATE Users SET 
            email=?, phone=?, aadhar_no=?, occupation=?, 
            city=?, area=?, flat_no=?,
            prev_address=?, emergency_contact=?,
            work_type=?, service_rate=?, profile_pic=?
            WHERE id=?
        '''
        
        conn.execute(update_query, (
            data.get('email'), data.get('phone'), data.get('aadhar'),
            data.get('occupation'), 
            data.get('city'), data.get('area'), data.get('flat_no'),
            data.get('prev_address'), data.get('emergency_contact'),
            data.get('work_type'), data.get('service_rate'), 
            filename, user_id
        ))
        
        conn.commit()
        conn.close()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('my_profile'))

    conn.close()
    return render_template('my_profile.html', user_info=user_data)

@app.route('/update_ticket_status', methods=['POST'])
def update_ticket_status():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    ticket_id = request.form.get('ticket_id')
    new_status = request.form.get('status')
    notes = request.form.get('completion_notes')
    file = request.files.get('completion_photo')

    conn = db.get_db_connection()

    if new_status == 'Resolved':
        if file and file.filename != '':
            filename = secure_filename(f"resolved_{ticket_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn.execute('UPDATE tickets SET status=?, completion_photo=?, completion_notes=? WHERE id=?', 
                         (new_status, filename, notes, ticket_id))
        else:
            flash("Proof photo is required!", "danger")
            return redirect(url_for('tech_dashboard'))
    else:
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id))

    conn.commit()
    conn.close()
    return redirect(url_for('tech_dashboard'))

@app.route('/owner/complaint_lifecycle')
def complaint_lifecycle():
    if 'user_id' not in session or session.get('role') != 'owner':
        return redirect(url_for('login'))
        
    conn = db.get_db_connection()
    query = '''
        SELECT t.*, u.name as tenant_name 
        FROM tickets t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.id DESC
    '''
    complaints = conn.execute(query).fetchall()
    conn.close()
    
    return render_template('complaint_lifecycle.html', complaints=complaints)


@app.route('/tenant/history')
def tenant_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = db.get_db_connection()
    
    try:
        # Fetch tickets with the Technician's name (if assigned)
        # We use t.* to get all ticket columns and u.name for the tech
        history = conn.execute('''
            SELECT t.*, u.name as tech_name 
            FROM tickets t
            LEFT JOIN Users u ON t.technician_id = u.id
            WHERE t.user_id = ? 
            ORDER BY t.created_at DESC
        ''', (user_id,)).fetchall()
    except Exception as e:
        print(f"Database Error: {e}")
        history = []
    finally:
        conn.close()

    return render_template('tenant_history.html', history=history)

@app.route('/verify_fix', methods=['POST'])
def verify_fix():
    ticket_id = request.form.get('ticket_id')
    
    conn = get_db_connection()
    # 1. Mark as verified by tenant
    # 2. Change status to 'Completed' so it moves to History
    conn.execute('''
        UPDATE tickets 
        SET status = 'Completed', verified_by_tenant = 1 
        WHERE id = ?
    ''', (ticket_id,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('tech_dashboard'))

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ticket_id = request.form.get('ticket_id')
    rating = request.form.get('rating')
    feedback_text = request.form.get('feedback_text')

    conn = db.get_db_connection()
    try:
        # We update the status to 'Completed' and save the feedback data
        conn.execute("""
            UPDATE tickets 
            SET status = 'Completed', 
                rating = ?, 
                feedback = ? 
            WHERE id = ?
        """, (rating, feedback_text, ticket_id))
        
        conn.commit()
        flash("Feedback submitted successfully! Ticket closed.", "success")
    except Exception as e:
        print(f"Error updating feedback: {e}")
        flash("An error occurred while submitting feedback.", "danger")
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/all_complaints')
def all_complaints():
    # 1. Security Check
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_owner_id = session['user_id']
    conn = db.get_db_connection()
    
    owner_name = "Owner"
    try:
        owner_data = conn.execute('SELECT name FROM owner WHERE id = ?', (current_owner_id,)).fetchone()
        if owner_data:
            owner_name = owner_data['name']
    except:
        owner_name = "Owner"

    query = '''
        SELECT t.id, t.ticket_id, t.issue_type, t.status, t.photo, t.description, 
               t.created_at, t.rating, t.feedback,
               u_tenant.name as tenant_name, u_tenant.area as tenant_area,
               u_tech.name as tech_name
        FROM tickets t
        JOIN Users u_tenant ON t.user_id = u_tenant.id
        LEFT JOIN Users u_tech ON t.technician_id = u_tech.id
        WHERE u_tenant.owner_id = ?
        ORDER BY t.created_at DESC
    '''
    
    complaints = conn.execute(query, (current_owner_id,)).fetchall()
    conn.close()
    
    return render_template('all_complaints.html', 
                           complaints=complaints, 
                           owner_name=owner_name)
    
     
def reset_ticket_status(ticket_id):
    # Connect to your database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Change the status back to 'Resolved' so the form shows up
    cursor.execute("UPDATE tickets SET status = 'Resolved' WHERE id = ?", (ticket_id,))
    
    conn.commit()
    conn.close()
    print(f"Success! Ticket #{ticket_id} is now 'Resolved'. Refresh your browser.")

# Put your ticket ID here (from your screenshot it was 8595)
reset_ticket_status(8595)

@app.route('/reject_task', methods=['POST'])
def reject_task():
    ticket_id = request.form.get('ticket_id')
    reason = request.form.get('reason')
    
    conn = db.get_db_connection()
    conn.execute('''
        UPDATE tickets 
        SET technician_id = NULL, status = 'Pending', 
        description = description || ' [REJECTED BY TECH: ' || ? || ']'
        WHERE id = ?
    ''', (reason, ticket_id))
    
    conn.commit()
    conn.close()
    
    flash("Task rejected and returned to Owner.", "info")
    return redirect(url_for('tech_dashboard'))

@app.route('/view_ticket/<int:ticket_id>')
def view_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = db.get_db_connection()
    ticket = conn.execute('''
        SELECT t.*, 
               u_tenant.name as tenant_name, u_tenant.area as tenant_area,
               u_tech.name as tech_name
        FROM tickets t
        JOIN Users u_tenant ON t.user_id = u_tenant.id
        LEFT JOIN Users u_tech ON t.technician_id = u_tech.id
        WHERE t.id = ?
    ''', (ticket_id,)).fetchone()
    conn.close()

    if not ticket:
        flash("Ticket not found!", "danger")
        return redirect(url_for('all_complaints'))
        
    return render_template('owner_view_ticket.html', t=ticket)
    
@app.route('/tenant/view_ticket/<int:ticket_id>')
def tenant_view_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = db.get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # Fetch ticket details
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ? AND user_id = ?', 
                         (ticket_id, session['user_id'])).fetchone()
    conn.close()

    if not ticket:
        return "Ticket not found or access denied", 404

    return render_template('tenant_view_ticket.html', ticket=ticket)
    
@app.route('/delete_ticket/<t_id>')
def delete_ticket(t_id):
    db.delete_ticket_from_db(t_id)
    return redirect(url_for('dashboard'))

@app.route('/add_property', methods=['POST'])
def add_property():
    society = request.form.get('society_name')
    city = request.form.get('city')
    state = request.form.get('state')
    country = request.form.get('country')
    towers = request.form.getlist('towers[]') 

    for tower in towers:
        db.execute('INSERT INTO buildings (society_name, house_no, city, state, country) VALUES (?, ?, ?, ?, ?)',
                   (society, tower, city, state, country))
    return redirect('/dashboard')

from itertools import groupby
from datetime import datetime

@app.route('/work_history')
def work_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    tasks = conn.execute('''
        SELECT 
            t.id, t.issue_type, t.description, t.created_at, 
            t.photo, t.completion_photo, t.completion_notes,
            t.feedback, t.rating,
            u.username as tenant_name,
            u.flat_no, u.area, u.city
        FROM tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.technician_id = ? AND t.status = 'Resolved'
        ORDER BY t.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    # Monthly Grouping Logic
    def get_month(task):
        try:
            from datetime import datetime
            dt = datetime.strptime(task['created_at'], '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%B %Y')
        except:
            return "Archives"

    from itertools import groupby
    grouped_tasks = {k: list(v) for k, v in groupby(tasks, get_month)}
    return render_template('work_history.html', grouped_tasks=grouped_tasks)

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    issue_type = request.form.get('issue_type')
    description = request.form.get('description')
    area = request.form.get('area') # <--- Make sure this is captured!
    
    conn = db.get_db_connection()
    conn.execute('''
        INSERT INTO tickets (issue_type, description, area, status, created_at, user_id) 
        VALUES (?, ?, ?, 'Pending', datetime('now', 'localtime'), ?)
    ''', (issue_type, description, area, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('tenant_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/complete_work/<int:ticket_id>', methods=['POST'])
def complete_work(ticket_id):
    notes = request.form.get('completion_notes')
    file = request.files.get('completion_photo')
    
    photo_name = None
    if file:
        photo_name = f"done_{ticket_id}.jpg"
        file.save(os.path.join('static/uploads/tickets', photo_name))

    conn = db.get_db_connection()
    conn.execute('''
        UPDATE tickets 
        SET status="Resolved", completion_notes=?, completion_photo=? 
        WHERE id=?
    ''', (notes, photo_name, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('tech_dash'))

@app.route('/helpbot', methods=['GET', 'POST'])
def helpbot():
    if 'user' not in session:
        return redirect(url_for('login'))

    bot_response = None
    user_query = None

    if request.method == 'POST':
        user_query = request.form.get('user_query')

        try:
    
            from openai import OpenAI

            client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are TrustFix property assistant"},
                    {"role": "user", "content": user_query}
                ]
            )

            bot_response = response.choices[0].message.content

        except Exception as e:
            print("ERROR:", e)
            bot_response = "Error occurred"

    return render_template('helpbot.html', bot_response=bot_response, user_query=user_query)

if __name__ == '__main__':
    app.run(debug=True)