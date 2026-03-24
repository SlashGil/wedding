import os
import secrets
import pandas as pd
from flask import (
    Blueprint, flash, redirect, render_template, request, url_for, current_app
)
from werkzeug.utils import secure_filename
from .auth import login_required
from .db import get_db, get_setting, set_setting

bp = Blueprint('admin', __name__, url_prefix='/admin')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bp.route('/', methods=('GET', 'POST'))
@login_required
def index():
    generated_link = None
    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        max_guests = request.form.get('max_guests', '1').strip()
        phone = request.form.get('phone', '').strip()
        kids_allowed = request.form.get('kids_allowed') == 'on'
        max_kids = request.form.get('max_kids', '0').strip()
        preferred_lang = request.form.get('preferred_lang', 'es')
        whatsapp_message = request.form.get('whatsapp_message', '').strip()

        if not guest_name:
            flash('Guest name is required.')
            return redirect(url_for('admin.index'))

        try:
            max_guests_int = max(1, int(max_guests))
            max_kids_int = max(0, int(max_kids))
        except ValueError:
            flash('Max guests and max kids must be valid numbers.')
            return redirect(url_for('admin.index'))

        if not kids_allowed: max_kids_int = 0
        token = secrets.token_urlsafe(10)

        with get_db() as conn:
            conn.execute(
                'INSERT INTO guests (guest_name, max_guests, kids_allowed, max_kids, token, phone, preferred_lang, whatsapp_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (guest_name, max_guests_int, kids_allowed, max_kids_int, token, phone, preferred_lang, whatsapp_message)
            )
        generated_link = url_for('main.invite', token=token, _external=True)
        flash(f'Invite created for {guest_name}.')

    with get_db() as conn:
        guest_links = conn.execute('SELECT * FROM guests ORDER BY id DESC').fetchall()
        rsvp_answers = conn.execute('SELECT r.id, r.name, r.attending, r.guests, r.kids, r.dietary_restrictions, r.created_at, g.guest_name AS invite_name FROM rsvps r LEFT JOIN guests g ON r.guest_token = g.token ORDER BY r.id DESC').fetchall()
        uploaded_photos = conn.execute('SELECT id, filename FROM photos ORDER BY id DESC').fetchall()

    current_hero_filename = get_setting('hero_image_filename')
    current_hero_url = url_for('static', filename='uploads/' + current_hero_filename) if current_hero_filename else None

    return render_template('admin.html', generated_link=generated_link, guest_links=guest_links, rsvp_answers=rsvp_answers, uploaded_photos=uploaded_photos, current_hero_url=current_hero_url)


@bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('admin.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('admin.index'))
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            df = pd.read_excel(file)
            required_cols = ['Name', 'Max Guests']
            if not all(col in df.columns for col in required_cols):
                flash(f'Missing required columns: {", ".join(required_cols)}')
                return redirect(url_for('admin.index'))

            with get_db() as conn:
                count = 0
                for _, row in df.iterrows():
                    guest_name = str(row['Name']).strip()
                    if not guest_name or guest_name == 'nan': continue
                    try: max_guests = max(1, int(row['Max Guests']))
                    except (ValueError, TypeError): max_guests = 1
                    phone = str(row.get('Phone', '')).strip()
                    if phone == 'nan': phone = ''
                    preferred_lang = str(row.get('Language', 'es')).strip().lower()
                    if preferred_lang not in ['en', 'es']: preferred_lang = 'es'
                    whatsapp_message = str(row.get('Message', '')).strip()
                    if whatsapp_message == 'nan': whatsapp_message = ''
                    kids_allowed = str(row.get('Kids Allowed', 'no')).strip().lower() in ['yes', 'true', '1', 'y']
                    max_kids = 0
                    if kids_allowed:
                        try: max_kids = max(0, int(row.get('Max Kids', 0)))
                        except (ValueError, TypeError): max_kids = 0
                    token = secrets.token_urlsafe(10)
                    conn.execute('INSERT INTO guests (guest_name, max_guests, kids_allowed, max_kids, token, phone, preferred_lang, whatsapp_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (guest_name, max_guests, kids_allowed, max_kids, token, phone, preferred_lang, whatsapp_message))
                    count += 1
            flash(f'Successfully imported {count} guests from {file.filename}.')
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
    else:
        flash('Invalid file format. Please upload an Excel file (.xlsx or .xls).')
    return redirect(url_for('admin.index'))


@bp.route('/guest/<int:guest_id>/update', methods=['POST'])
@login_required
def update_guest(guest_id):
    guest_name = request.form.get('guest_name', '').strip()
    max_guests = request.form.get('max_guests', '1').strip()
    phone = request.form.get('phone', '').strip()
    kids_allowed = request.form.get('kids_allowed') == 'on'
    max_kids = request.form.get('max_kids', '0').strip()
    preferred_lang = request.form.get('preferred_lang', 'es')
    whatsapp_message = request.form.get('whatsapp_message', '').strip()

    if not guest_name:
        flash('Guest name is required to update an invite.')
        return redirect(url_for('admin.index'))

    try:
        max_guests_int = max(1, int(max_guests))
        max_kids_int = max(0, int(max_kids))
    except ValueError:
        flash('Max guests and max kids must be valid numbers.')
        return redirect(url_for('admin.index'))

    if not kids_allowed: max_kids_int = 0

    with get_db() as conn:
        conn.execute('UPDATE guests SET guest_name = ?, max_guests = ?, kids_allowed = ?, max_kids = ?, phone = ?, preferred_lang = ?, whatsapp_message = ? WHERE id = ?', (guest_name, max_guests_int, kids_allowed, max_kids_int, phone, preferred_lang, whatsapp_message, guest_id))
    flash(f'Invite updated for {guest_name}.')
    return redirect(url_for('admin.index'))


@bp.route('/guest/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete_guest(guest_id):
    with get_db() as conn:
        guest = conn.execute('SELECT guest_name, token FROM guests WHERE id = ?', (guest_id,)).fetchone()
        if not guest:
            flash('Guest invite not found.')
            return redirect(url_for('admin.index'))
        conn.execute('DELETE FROM guests WHERE id = ?', (guest_id,))
        conn.execute('DELETE FROM rsvps WHERE guest_token = ?', (guest['token'],))
    flash(f"Invite deleted for {guest['guest_name']}.")
    return redirect(url_for('admin.index'))


@bp.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    if 'photo' not in request.files or request.files['photo'].filename == '':
        flash('No selected file')
        return redirect(url_for('admin.index'))

    file = request.files['photo']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            flash(f'A photo named "{filename}" already exists. Please rename your file and try again.')
            return redirect(url_for('admin.index'))
        try:
            file.save(file_path)
            with get_db() as conn:
                conn.execute('INSERT INTO photos (filename) VALUES (?)', (filename,))
            flash(f'Photo "{filename}" uploaded successfully.')
        except Exception as e:
            flash(f'An error occurred: {str(e)}')
    else:
        flash(f'Invalid file type. Allowed types are: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}.')
    return redirect(url_for('admin.index'))


@bp.route('/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    with get_db() as conn:
        photo = conn.execute('SELECT filename FROM photos WHERE id = ?', (photo_id,)).fetchone()
        if not photo:
            flash('Photo not found.')
            return redirect(url_for('admin.index'))
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
            conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
            flash(f"Photo '{photo['filename']}' deleted successfully.")
        except Exception as e:
            flash(f"Error deleting photo: {str(e)}")
    return redirect(url_for('admin.index'))


@bp.route('/upload_hero', methods=['POST'])
@login_required
def upload_hero():
    if 'hero_image' not in request.files or request.files['hero_image'].filename == '':
        flash('No file selected for hero image.')
        return redirect(url_for('admin.index'))

    file = request.files['hero_image']
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"hero_{secrets.token_hex(8)}.{ext}"
        file_path = os.path.join(current_app.config['HERO_UPLOAD_FOLDER'], filename)
        old_filename = get_setting('hero_image_filename')
        try:
            file.save(file_path)
            set_setting('hero_image_filename', filename)
            flash('Hero image updated successfully.')
            if old_filename:
                old_file_path = os.path.join(current_app.config['HERO_UPLOAD_FOLDER'], old_filename)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
        except Exception as e:
            flash(f'An error occurred while updating hero image: {str(e)}')
    else:
        flash(f'Invalid file type for hero image. Allowed: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}.')
    return redirect(url_for('admin.index'))