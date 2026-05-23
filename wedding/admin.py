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

        photo_response = supabase.from_('photos').select('id, filename, is_visible, is_featured').order('is_featured', desc=True).order('position').execute()
        if photo_response.data:
            photo_paths = [f"photos/{p['filename']}" for p in photo_response.data]
            transform_options = {'width': 200, 'height': 200, 'resize': 'cover', 'quality': 60}
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

@bp.route('/photos/reorder', methods=['POST'])
@login_required
def reorder_photos():
    supabase = get_supabase_client()
    ordered_ids = request.json.get('order', [])
    
    if not ordered_ids:
        return jsonify({'status': 'error', 'message': 'No order provided.'}), 400

    try:
        for index, photo_id in enumerate(ordered_ids):
            supabase.from_('photos').update({'position': index}).eq('id', photo_id).execute()
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.error(f"Error reordering photos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
    supabase = get_supabase_client()
    guest_links = []
    total_invitations = 0
    total_guests = 0
    total_kids = 0
    whatsapp_message = get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}')
    
    try:
        guest_response = supabase.from_('guests').select('*, sent_by_admin:admins(username)').order('id', desc=True).execute()
        guest_links = guest_response.data
        
        total_invitations = len(guest_links)
        total_guests = sum(g.get('max_guests', 0) for g in guest_links)
        total_kids = sum(g.get('max_kids', 0) for g in guest_links if g.get('kids_allowed'))

        for guest in guest_links:
            guest['phone_number_display'] = format_phone_for_display(guest.get('phone_number'))
            admin = guest.get('sent_by_admin')
            guest['sent_by_username'] = admin['username'] if isinstance(admin, dict) else None

    except Exception as e:
        current_app.logger.error(f"Error fetching guests from Supabase: {e}")
        flash(f"Error loading guests: {str(e)}", 'danger')
        
    return render_template('guests.html', 
                           guest_links=guest_links, 
                           whatsapp_message=whatsapp_message,
                           total_invitations=total_invitations,
                           total_guests=total_guests,
                           total_kids=total_kids)

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

@bp.route('/upload_single_photo_ajax', methods=['POST'])
@login_required
def upload_single_photo_ajax():
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']
    
    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': 'No photo file found in request.'}), 400

    file = request.files['photo']
    if not (file and allowed_file(file.filename)):
        return jsonify({'status': 'error', 'message': 'Invalid file type.'}), 400

    filename = secure_filename(file.filename)
    file_content = file.read()
    path_on_storage = f"photos/{filename}"
    
    try:
        supabase.storage.from_(bucket_name).upload(path_on_storage, file_content)
        supabase.from_('photos').insert({'filename': filename, 'is_visible': True}).execute()
        current_app.logger.info(f"Successfully uploaded and registered '{filename}'.")
        return jsonify({'status': 'success', 'filename': filename})
    except Exception as e:
        current_app.logger.error(f"Failed to upload '{filename}': {e}")
        try:
            supabase.storage.from_(bucket_name).remove([path_on_storage])
        except Exception as cleanup_e:
            current_app.logger.error(f"CRITICAL: Failed to clean up orphaned file '{path_on_storage}' after a failed DB insert. Error: {cleanup_e}")
        return jsonify({'status': 'error', 'message': str(e), 'filename': filename}), 500

@bp.route('/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']

    try:
        photo_response = supabase.from_('photos').select('filename').eq('id', photo_id).execute()
        
        if not photo_response.data:
            flash('Photo not found in database.', 'danger')
        else:
            filename = photo_response.data[0]['filename']
            
            supabase.from_('photos').delete().eq('id', photo_id).execute()
            
            try:
                path_on_storage = f"photos/{filename}"
                supabase.storage.from_(bucket_name).remove([path_on_storage])
                flash(f"Photo '{filename}' deleted successfully.", 'success')
            except Exception as storage_e:
                current_app.logger.warning(f"Photo '{filename}' deleted from DB, but couldn't be removed from storage. Error: {storage_e}")
                flash(f"Photo '{filename}' deleted from database.", 'info')

    except Exception as e:
        current_app.logger.error(f"Error during photo deletion process: {e}")
        flash(f"An error occurred while deleting the photo: {str(e)}", 'danger')
        
    return redirect(url_for('admin.index'))

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

@bp.route('/photo/<int:photo_id>/toggle_featured', methods=['POST'])
@login_required
def toggle_featured(photo_id):
    supabase = get_supabase_client()
    try:
        photo = supabase.from_('photos').select('is_featured').eq('id', photo_id).single().execute()
        if not photo.data:
            return jsonify({'status': 'error', 'message': 'Photo not found.'}), 404
        
        new_featured_state = not photo.data.get('is_featured', False)
        
        supabase.from_('photos').update({'is_featured': new_featured_state}).eq('id', photo_id).execute()
        
        return jsonify({'status': 'success', 'new_featured_state': new_featured_state})

    except Exception as e:
        current_app.logger.error(f"Error toggling featured state for photo {photo_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/upload_hero', methods=['POST'])
@login_required
def upload_hero():
    # ... (code remains the same)
    pass