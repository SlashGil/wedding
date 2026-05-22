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

def get_image_url(path, transform_params):
    """Builds a Cloudflare-proxied image URL."""
    base_url = f"https://{current_app.config['CLOUDFLARE_DOMAIN']}/{current_app.config['SUPABASE_BUCKET']}/{path}"
    params = '&'.join([f'{k}={v}' for k, v in transform_params.items()])
    return f"{base_url}?{params}"

def generate_whatsapp_link(message, guest_name, invite_link, phone_number=None):
    final_message = message.replace('{guest_name}', guest_name).replace('{invite_link}', invite_link)
    if phone_number:
        return f"https://wa.me/{phone_number}?text={quote_plus(final_message)}"
    return f"https://wa.me/?text={quote_plus(final_message)}"


@bp.route('/', methods=('GET', 'POST'))
@login_required
def index():
    supabase = get_supabase_client()
    
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
        
        if 'update_gallery_settings' in request.form:
            initial_photos = request.form.get('gallery_initial_photos', '6')
            set_setting('gallery_initial_photos', initial_photos)
            flash('Gallery display settings updated.', 'success')
            return redirect(url_for('admin.index'))

    rsvp_answers, uploaded_photos = [], []
    try:
        rsvp_response = supabase.from_('rsvps').select('id,name,attending,guests,kids,dietary_restrictions,created_at,invited_guest:guests(guest_name)').order('id', desc=True).execute()
        for rsvp in rsvp_response.data:
            invited_guest = rsvp.get('invited_guest') if isinstance(rsvp.get('invited_guest'), dict) else {}
            rsvp_answers.append({**rsvp, 'invite_name': invited_guest.get('guest_name') or 'N/A'})

        photo_response = supabase.from_('photos').select('id, filename, is_visible').order('id', desc=True).execute()
        if photo_response.data:
            for photo_data in photo_response.data:
                transform = {'width': 200, 'height': 200, 'resize': 'cover', 'quality': 70}
                photo_data['url'] = get_image_url(f"photos/{photo_data['filename']}", transform)
                uploaded_photos.append(photo_data)

    except Exception as e:
        current_app.logger.error(f"Error fetching data from Supabase: {e}")
        flash(f"Error loading data: {str(e)}", 'danger')

    current_hero_url = None
    current_hero_filename = get_setting('hero_image_filename')
    if current_hero_filename:
        try:
            transform = {'width': 800, 'resize': 'contain', 'quality': 75}
            current_hero_url = get_image_url(f"uploads/{current_hero_filename}", transform)
        except Exception as e:
            current_app.logger.error(f"Error generating hero image URL: {e}")

    gallery_initial_photos = get_setting('gallery_initial_photos', '6')

    return render_template('admin.html', 
                           rsvp_answers=rsvp_answers, 
                           uploaded_photos=uploaded_photos, 
                           current_hero_url=current_hero_url, 
                           dress_code_es=get_setting('dress_code_es', 'Formal / Etiqueta Opcional'), 
                           dress_code_en=get_setting('dress_code_en', 'Formal / Black-Tie Optional'), 
                           pinterest_links={'women': get_setting('pinterest_women', ''), 'men': get_setting('pinterest_men', '')}, 
                           whatsapp_message=get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}'),
                           gallery_initial_photos=gallery_initial_photos)

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

@bp.route('/upload_hero', methods=['POST'])
@login_required
def upload_hero():
    # ... (code remains the same)
    pass