import os
import secrets
import pandas as pd
from io import BytesIO
from urllib.parse import quote_plus
from datetime import datetime, timezone
import zipfile
from flask import (
    Blueprint, flash, redirect, render_template, request, url_for, current_app, session, send_file, jsonify
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from .auth import login_required
from .db import get_supabase_client, get_setting, set_setting

bp = Blueprint('admin', __name__, url_prefix='/admin')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def sanitize_and_normalize_phone(phone_number_str):
    if not phone_number_str:
        return ""
    digits = ''.join(filter(str.isdigit, str(phone_number_str)))
    known_codes = ['52', '1', '41', '34', '47']
    for code in known_codes:
        if digits.startswith(code) and len(digits) > 10:
            return digits
    if len(digits) == 10:
        return '52' + digits
    return digits

def format_phone_for_display(phone_digits_str):
    if not phone_digits_str or not str(phone_digits_str).isdigit():
        return phone_digits_str
    return f"+{phone_digits_str}"

def generate_whatsapp_link(message, guest_name, invite_link, phone_number=None):
    final_message = message.replace('{guest_name}', guest_name).replace('{invite_link}', invite_link)
    if phone_number:
        return f"https://wa.me/{phone_number}?text={quote_plus(final_message)}"
    return f"https://wa.me/?text={quote_plus(final_message)}"


@bp.route('/', methods=('GET', 'POST'))
@login_required
def index():
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']
    
    if request.method == 'POST':
        if 'update_whatsapp_message' in request.form:
            set_setting('whatsapp_message', request.form.get('whatsapp_message', '').strip())
            flash('Default WhatsApp message updated.', 'success')
            return redirect(url_for('admin.index'))
        
        if 'update_pinterest_links' in request.form:
            set_setting('pinterest_women', request.form.get('pinterest_women', '').strip())
            set_setting('pinterest_men', request.form.get('pinterest_men', '').strip())
            flash('Pinterest links updated successfully.', 'success')
            return redirect(url_for('admin.index'))

    rsvp_answers, uploaded_photos = [], []
    try:
        rsvp_response = supabase.from_('rsvps').select('id,name,attending,guests,kids,dietary_restrictions,created_at,invited_guest:guests(guest_name)').order('id', desc=True).execute()
        for rsvp in rsvp_response.data:
            invited_guest = rsvp.get('invited_guest') if isinstance(rsvp.get('invited_guest'), dict) else {}
            rsvp_answers.append({**rsvp, 'invite_name': invited_guest.get('guest_name') or 'N/A'})

        photo_response = supabase.from_('photos').select('id, filename, is_visible').order('id', desc=True).execute()
        if photo_response.data:
            photo_paths = [f"photos/{p['filename']}" for p in photo_response.data]
            transform_options = {'width': 200, 'height': 200, 'resize': 'cover'}
            signed_urls_response = supabase.storage.from_(bucket_name).create_signed_urls(photo_paths, 3600, options={'transform': transform_options})
            url_map = {os.path.basename(item['path']): item['signedURL'] for item in signed_urls_response if not item.get('error')}
            for photo_data in photo_response.data:
                if photo_data['filename'] in url_map:
                    uploaded_photos.append({**photo_data, 'url': url_map[photo_data['filename']]})
    except Exception as e:
        current_app.logger.error(f"Error fetching data from Supabase: {e}")
        flash(f"Error loading data: {str(e)}", 'danger')

    current_hero_url = None
    current_hero_filename = get_setting('hero_image_filename')
    if current_hero_filename:
        try:
            transform_options = {'width': 800, 'resize': 'contain', 'quality': 75}
            signed_url_response = supabase.storage.from_(bucket_name).create_signed_url(f"uploads/{current_hero_filename}", 3600, options={'transform': transform_options})
            current_hero_url = signed_url_response['signedURL']
        except Exception as e:
            current_app.logger.error(f"Error fetching hero image URL: {e}")

    return render_template('admin.html', 
                           rsvp_answers=rsvp_answers, 
                           uploaded_photos=uploaded_photos, 
                           current_hero_url=current_hero_url, 
                           dress_code_es=get_setting('dress_code_es', 'Formal / Etiqueta Opcional'), 
                           dress_code_en=get_setting('dress_code_en', 'Formal / Black-Tie Optional'), 
                           pinterest_links={'women': get_setting('pinterest_women', ''), 'men': get_setting('pinterest_men', '')}, 
                           whatsapp_message=get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}'))

@bp.route('/rsvps/export')
@login_required
def export_rsvps():
    # ... (code remains the same)
    pass

@bp.route('/users')
@login_required
def manage_users():
    # ... (code remains the same)
    pass

@bp.route('/users/new', methods=('GET', 'POST'))
@login_required
def new_user():
    # ... (code remains the same)
    pass

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    # ... (code remains the same)
    pass

@bp.route('/guests')
@login_required
def manage_guests():
    # ... (code remains the same)
    pass

@bp.route('/guest/<int:guest_id>/mark_sent', methods=['POST'])
@login_required
def mark_sent(guest_id):
    # ... (code remains the same)
    pass

@bp.route('/guests/new', methods=('GET', 'POST'))
@login_required
def new_guest():
    # ... (code remains the same)
    pass

@bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    # ... (code remains the same)
    pass

@bp.route('/guest/<int:guest_id>/update', methods=['POST'])
@login_required
def update_guest(guest_id):
    # ... (code remains the same)
    pass

@bp.route('/guest/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete_guest(guest_id):
    # ... (code remains the same)
    pass

@bp.route('/upload_photos_ajax', methods=['POST'])
@login_required
def upload_photos_ajax():
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']
    
    successful_files = []
    failed_files = []
    files_to_process = []
    
    source = "unknown"
    if 'zip_file' in request.files:
        source = "ZIP file"
        zip_file = request.files['zip_file']
        if zip_file and zip_file.filename.endswith('.zip'):
            try:
                with zipfile.ZipFile(BytesIO(zip_file.read())) as z:
                    for filename in z.namelist():
                        if not filename.startswith('__MACOSX') and allowed_file(filename):
                            files_to_process.append((secure_filename(filename), z.read(filename)))
            except zipfile.BadZipFile:
                current_app.logger.error("Upload failed: Invalid ZIP file provided.")
                return jsonify({'error': 'Invalid ZIP file.'}), 400
    
    elif 'photos[]' in request.files:
        source = "direct file upload"
        uploaded_files = request.files.getlist('photos[]')
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                files_to_process.append((secure_filename(file.filename), file.read()))

    if not files_to_process:
        current_app.logger.warning("Photo upload endpoint called but no valid files were processed.")
        return jsonify({'error': 'No valid files to process.'}), 400

    current_app.logger.info(f"Starting multi-photo upload from {source}. Processing {len(files_to_process)} files.")

    for filename, file_content in files_to_process:
        path_on_storage = f"photos/{filename}"
        try:
            supabase.storage.from_(bucket_name).upload(path_on_storage, file_content)
            supabase.from_('photos').insert({'filename': filename, 'is_visible': True}).execute()
            successful_files.append(filename)
            current_app.logger.info(f"Successfully uploaded and registered '{filename}'.")
        except Exception as e:
            failed_files.append(filename)
            current_app.logger.error(f"Failed to upload '{filename}': {e}")
            try:
                supabase.storage.from_(bucket_name).remove([path_on_storage])
            except Exception as cleanup_e:
                current_app.logger.error(f"CRITICAL: Failed to clean up orphaned file '{path_on_storage}' after a failed DB insert. Error: {cleanup_e}")

    summary_message = f"Multi-upload complete. Success: {len(successful_files)}, Failed: {len(failed_files)}."
    current_app.logger.info(summary_message)

    return jsonify({
        'successful_files': successful_files,
        'failed_files': failed_files
    })

@bp.route('/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    # ... (code remains the same)
    pass

@bp.route('/photo/<int:photo_id>/toggle_visibility', methods=['POST'])
@login_required
def toggle_photo_visibility(photo_id):
    supabase = get_supabase_client()
    try:
        photo_response = supabase.from_('photos').select('is_visible').eq('id', photo_id).execute()
        if not photo_response.data:
            return jsonify({'status': 'error', 'message': 'Photo not found.'}), 404
        
        current_visibility = photo_response.data[0].get('is_visible', True)
        new_visibility = not current_visibility
        
        supabase.from_('photos').update({'is_visible': new_visibility}).eq('id', photo_id).execute()
        
        return jsonify({'status': 'success', 'new_visibility': new_visibility})
        
    except Exception as e:
        current_app.logger.error(f"Error toggling photo visibility: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/upload_hero', methods=['POST'])
@login_required
def upload_hero():
    # ... (code remains the same)
    pass