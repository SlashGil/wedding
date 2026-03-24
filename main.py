from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import secrets
import os
from functools import wraps
import pandas as pd

app = Flask(__name__)
# Use an environment variable for the secret key in production for security
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a-super-secret-key-for-dev-only')

DATABASE = 'rsvp.db'
ADMIN_USERNAME = os.environ.get('WEDDING_ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('WEDDING_ADMIN_PASSWORD', 'wedding2026')


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please login to access the admin panel.')
            return redirect(url_for('admin_login'))
        return view_func(*args, **kwargs)

    return wrapped


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table_name, column_name, definition):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {col[1] for col in columns}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS guests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_name TEXT NOT NULL,
                max_guests INTEGER NOT NULL DEFAULT 1,
                kids_allowed BOOLEAN NOT NULL DEFAULT 0,
                max_kids INTEGER NOT NULL DEFAULT 0,
                token TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                attending BOOLEAN NOT NULL,
                guests INTEGER NOT NULL,
                kids INTEGER NOT NULL DEFAULT 0,
                dietary_restrictions TEXT,
                guest_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Lightweight migration for old database versions
        ensure_column(conn, 'rsvps', 'kids', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'rsvps', 'guest_token', 'TEXT')
        ensure_column(conn, 'rsvps', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')


@app.route('/')
def index():
    guest_name = request.args.get('name', '').strip()
    allowed_guests = request.args.get('guests', '1')

    guest = {
        'token': None,
        'guest_name': guest_name,
        'max_guests': int(allowed_guests) if str(allowed_guests).isdigit() else 1,
        'kids_allowed': False,
        'max_kids': 0,
    }

    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None)


@app.route('/invite/<token>')
def invite(token):
    with get_db() as conn:
        guest = conn.execute('SELECT * FROM guests WHERE token = ?', (token,)).fetchone()

    if not guest:
        flash('This invite link is invalid. Please contact the couple.')
        return redirect(url_for('index'))

    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None)


@app.route('/rsvp', methods=['POST'])
def rsvp():
    token = request.form.get('guest_token', '').strip()
    name = request.form.get('name', '').strip()
    attending = request.form.get('attending') == 'yes'

    if not name:
        flash('Please enter your name.')
        return redirect(request.referrer or url_for('index'))

    with get_db() as conn:
        guest = conn.execute('SELECT * FROM guests WHERE token = ?', (token,)).fetchone() if token else None

        max_guests = int(guest['max_guests']) if guest else 10
        kids_allowed = bool(guest['kids_allowed']) if guest else False
        max_kids = int(guest['max_kids']) if guest else 0

        try:
            guests = int(request.form.get('guests', 1))
            kids = int(request.form.get('kids', 0))
        except ValueError:
            flash('Please provide valid numbers for guests and kids.')
            return redirect(request.referrer or url_for('index'))

        if guests < 1:
            guests = 1
        if guests > max_guests:
            guests = max_guests

        if kids < 0:
            kids = 0
        if not kids_allowed:
            kids = 0
        elif kids > max_kids:
            kids = max_kids

        dietary = request.form.get('dietary_restrictions', '').strip()

        conn.execute(
            'INSERT INTO rsvps (name, attending, guests, kids, dietary_restrictions, guest_token) VALUES (?, ?, ?, ?, ?, ?)',
            (name, attending, guests, kids, dietary, token if token else None)
        )

    if guest:
        submitted_data = {
            'name': name,
            'attending': attending,
            'guests': guests,
            'kids': kids,
            'kids_allowed': kids_allowed,
        }
        return render_template('index.html', guest=guest, rsvp_submitted=True, submitted_data=submitted_data)

    flash('Thank you for your RSVP!')
    return redirect(url_for('index', name=name, guests=guests))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Welcome to the admin panel.')
            return redirect(url_for('admin'))

        flash('Invalid username or password.')

    return render_template('admin_login.html')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('You have been logged out.')
    return redirect(url_for('admin_login'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    generated_link = None

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        max_guests = request.form.get('max_guests', '1').strip()
        kids_allowed = request.form.get('kids_allowed') == 'on'
        max_kids = request.form.get('max_kids', '0').strip()

        if not guest_name:
            flash('Guest name is required.')
            return redirect(url_for('admin'))

        try:
            max_guests_int = max(1, int(max_guests))
            max_kids_int = max(0, int(max_kids))
        except ValueError:
            flash('Max guests and max kids must be valid numbers.')
            return redirect(url_for('admin'))

        if not kids_allowed:
            max_kids_int = 0

        token = secrets.token_urlsafe(10)

        with get_db() as conn:
            conn.execute(
                'INSERT INTO guests (guest_name, max_guests, kids_allowed, max_kids, token) VALUES (?, ?, ?, ?, ?)',
                (guest_name, max_guests_int, kids_allowed, max_kids_int, token)
            )

        generated_link = url_for('invite', token=token, _external=True)
        flash(f'Invite created for {guest_name}.')

    with get_db() as conn:
        guest_links = conn.execute('SELECT * FROM guests ORDER BY id DESC').fetchall()
        rsvp_answers = conn.execute('''
            SELECT
                r.id,
                r.name,
                r.attending,
                r.guests,
                r.kids,
                r.dietary_restrictions,
                r.created_at,
                g.guest_name AS invite_name
            FROM rsvps r
            LEFT JOIN guests g ON r.guest_token = g.token
            ORDER BY r.id DESC
        ''').fetchall()

    return render_template(
        'admin.html',
        generated_link=generated_link,
        guest_links=guest_links,
        rsvp_answers=rsvp_answers
    )


@app.route('/admin/upload', methods=['POST'])
@login_required
def admin_upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('admin'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('admin'))
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            df = pd.read_excel(file)
            
            # Expected columns: 'Name', 'Max Guests', 'Kids Allowed' (Optional), 'Max Kids' (Optional)
            required_cols = ['Name', 'Max Guests']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                flash(f'Missing required columns: {", ".join(missing_cols)}')
                return redirect(url_for('admin'))

            with get_db() as conn:
                count = 0
                for index, row in df.iterrows():
                    guest_name = str(row['Name']).strip()
                    if not guest_name or guest_name == 'nan':
                        continue
                        
                    try:
                        max_guests = max(1, int(row['Max Guests']))
                    except (ValueError, TypeError):
                        max_guests = 1
                        
                    kids_allowed = False
                    if 'Kids Allowed' in df.columns:
                        val = str(row['Kids Allowed']).strip().lower()
                        kids_allowed = val in ['yes', 'true', '1', 'y']
                        
                    max_kids = 0
                    if kids_allowed and 'Max Kids' in df.columns:
                        try:
                            max_kids = max(0, int(row['Max Kids']))
                        except (ValueError, TypeError):
                            max_kids = 0
                            
                    token = secrets.token_urlsafe(10)
                    
                    conn.execute(
                        'INSERT INTO guests (guest_name, max_guests, kids_allowed, max_kids, token) VALUES (?, ?, ?, ?, ?)',
                        (guest_name, max_guests, kids_allowed, max_kids, token)
                    )
                    count += 1
                    
            flash(f'Successfully imported {count} guests from {file.filename}.')
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
    else:
        flash('Invalid file format. Please upload an Excel file (.xlsx or .xls).')
        
    return redirect(url_for('admin'))


@app.route('/admin/guest/<int:guest_id>/update', methods=['POST'])
@login_required
def update_guest(guest_id):
    guest_name = request.form.get('guest_name', '').strip()
    max_guests = request.form.get('max_guests', '1').strip()
    kids_allowed = request.form.get('kids_allowed') == 'on'
    max_kids = request.form.get('max_kids', '0').strip()

    if not guest_name:
        flash('Guest name is required to update an invite.')
        return redirect(url_for('admin'))

    try:
        max_guests_int = max(1, int(max_guests))
        max_kids_int = max(0, int(max_kids))
    except ValueError:
        flash('Max guests and max kids must be valid numbers.')
        return redirect(url_for('admin'))

    if not kids_allowed:
        max_kids_int = 0

    with get_db() as conn:
        conn.execute(
            'UPDATE guests SET guest_name = ?, max_guests = ?, kids_allowed = ?, max_kids = ? WHERE id = ?',
            (guest_name, max_guests_int, kids_allowed, max_kids_int, guest_id)
        )

    flash(f'Invite updated for {guest_name}.')
    return redirect(url_for('admin'))


@app.route('/admin/guest/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete_guest(guest_id):
    with get_db() as conn:
        guest = conn.execute('SELECT guest_name, token FROM guests WHERE id = ?', (guest_id,)).fetchone()

        if not guest:
            flash('Guest invite not found.')
            return redirect(url_for('admin'))

        conn.execute('DELETE FROM guests WHERE id = ?', (guest_id,))
        conn.execute('DELETE FROM rsvps WHERE guest_token = ?', (guest['token'],))

    flash(f"Invite deleted for {guest['guest_name']}.")
    return redirect(url_for('admin'))


if __name__ == '__main__':
    # Initialize the database and create the table if it doesn't exist
    init_db()
    # This block is for local development.
    # In production, a WSGI server like Gunicorn runs the app.
    # The 'PORT' env var is used by hosting providers like Render.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
