import os
import secrets
import pandas as pd
from io import BytesIO
from urllib.parse import quote
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
    encoded_message = quote(final_message, encoding='utf-8')
    if phone_number:
        return f"https://wa.me/{phone_number}?text={encoded_message}"
    return f"https://wa.me/?text={encoded_message}"


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

    uploaded_photos = []
    try:
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
                           uploaded_photos=uploaded_photos, 
                           current_hero_url=current_hero_url, 
                           dress_code_es=get_setting('dress_code_es', 'Formal / Etiqueta Opcional'), 
                           dress_code_en=get_setting('dress_code_en', 'Formal / Black-Tie Optional'), 
                           pinterest_links={'women': get_setting('pinterest_women', ''), 'men': get_setting('pinterest_men', '')}, 
                           whatsapp_message=get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}'))

@bp.route('/gift_registry/update', methods=['POST'])
@login_required
def update_gift_registry():
    clabe = request.form.get('gift_bank_clabe', '').strip()
    details_es = request.form.get('gift_bank_details_es', '').strip()
    details_en = request.form.get('gift_bank_details_en', '').strip()
    
    set_setting('gift_bank_clabe', clabe)
    set_setting('gift_bank_details_es', details_es)
    set_setting('gift_bank_details_en', details_en)
    
    flash('Gift registry bank settings updated successfully.', 'success')
    return redirect(url_for('admin.index'))

@bp.route('/gift_registry/toggle', methods=['POST'])
@login_required
def toggle_gift_registry():
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        set_setting('gift_bank_enabled', 'true' if enabled else 'false')
        return jsonify({'status': 'success', 'enabled': enabled})
    except Exception as e:
        current_app.logger.error(f"Error toggling gift registry: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@bp.route('/users')
@login_required
def manage_users():
    supabase = get_supabase_client()
    try:
        users_response = supabase.from_('admins').select('id, username').execute()
        users = users_response.data
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}")
        flash(f"Error loading users: {str(e)}", 'danger')
        users = []
    return render_template('users.html', users=users)

@bp.route('/users/new', methods=('GET', 'POST'))
@login_required
def new_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('new_user.html')
            
        try:
            supabase = get_supabase_client()
            hashed_password = generate_password_hash(password)
            supabase.from_('admins').insert({
                'username': username,
                'password_hash': hashed_password
            }).execute()
            flash(f'User "{username}" created successfully.', 'success')
            return redirect(url_for('admin.manage_users'))
        except Exception as e:
            current_app.logger.error(f"Error creating user: {e}")
            flash(f'Error creating user: {str(e)}', 'danger')
            
    return render_template('new_user.html')

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash("You cannot delete your own account.", 'danger')
        return redirect(url_for('admin.manage_users'))
        
    try:
        supabase = get_supabase_client()
        supabase.from_('admins').delete().eq('id', user_id).execute()
        flash('User deleted successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting user: {e}")
        flash(f'Error deleting user: {str(e)}', 'danger')
        
    return redirect(url_for('admin.manage_users'))

@bp.route('/guests')
@login_required
def manage_guests():
    supabase = get_supabase_client()
    guest_links = []
    total_invitations = 0
    total_guests = 0
    total_kids = 0
    
    default_es = 'Hola {guest_name}, te invitamos a nuestra boda! Confirma tu asistencia aquí: {invite_link}'
    default_en = 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}'
    
    whatsapp_message_es = get_setting('whatsapp_message_es', default_es)
    whatsapp_message_en = get_setting('whatsapp_message_en', default_en)
    
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
                           whatsapp_message_es=whatsapp_message_es,
                           whatsapp_message_en=whatsapp_message_en,
                           total_invitations=total_invitations,
                           total_guests=total_guests,
                           total_kids=total_kids)

@bp.route('/guests/update_whatsapp', methods=['POST'])
@login_required
def update_whatsapp_templates():
    message_es = request.form.get('whatsapp_message_es', '')
    message_en = request.form.get('whatsapp_message_en', '')
    set_setting('whatsapp_message_es', message_es)
    set_setting('whatsapp_message_en', message_en)
    flash('WhatsApp message templates have been updated.', 'success')
    return redirect(url_for('admin.manage_guests'))

@bp.route('/guest/<int:guest_id>/mark_sent', methods=['POST'])
@login_required
def mark_sent(guest_id):
    supabase = get_supabase_client()
    admin_id = session.get('user_id')
    
    try:
        supabase.from_('guests').update({
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'sent_by_admin_id': admin_id
        }).eq('id', guest_id).execute()
        return jsonify({'status': 'success', 'message': 'Marked as sent.'})
    except Exception as e:
        current_app.logger.error(f"Error marking guest as sent: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/guests/new', methods=('GET', 'POST'))
@login_required
def new_guest():
    supabase = get_supabase_client()
    new_invite_info = None
    
    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        max_guests = request.form.get('max_guests', 1, type=int)
        max_kids = request.form.get('max_kids', 0, type=int)
        kids_allowed = 'kids_allowed' in request.form
        
        if not guest_name:
            flash('Guest name is required.', 'danger')
            return render_template('new_guest.html', new_invite_info=None)
        
        try:
            # Sanitize phone number
            normalized_phone = sanitize_and_normalize_phone(phone_number) if phone_number else None
            
            # Generate unique token
            token = secrets.token_urlsafe(32)
            
            # Create guest record
            guest_data = {
                'guest_name': guest_name,
                'token': token,
                'max_guests': max_guests,
                'kids_allowed': kids_allowed,
                'max_kids': max_kids if kids_allowed else 0,
                'phone_number': normalized_phone,
                'sent_by_admin_id': session.get('user_id')
            }
            
            response = supabase.from_('guests').insert(guest_data).execute()
            
            if response.data:
                # Generate invite link
                invite_link = f"{request.url_root}rsvp/{token}"
                
                new_invite_info = {
                    'guest_name': guest_name,
                    'invite_link': invite_link,
                    'phone_number': normalized_phone
                }
                
                flash(f'Invitation created successfully for {guest_name}!', 'success')
            else:
                flash('Error creating invitation.', 'danger')
                
        except Exception as e:
            current_app.logger.error(f"Error creating guest invitation: {e}")
            flash(f'Error creating invitation: {str(e)}', 'danger')
    
    return render_template('new_guest.html', new_invite_info=new_invite_info)

@bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'excel_file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('admin.manage_guests'))
    
    file = request.files['excel_file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('admin.manage_guests'))
        
    if file and file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file)
            supabase = get_supabase_client()
            
            for _, row in df.iterrows():
                guest_name = row.get('Guest Name')
                if not guest_name:
                    continue

                phone_number = row.get('Phone Number')
                normalized_phone = sanitize_and_normalize_phone(phone_number) if pd.notna(phone_number) else None
                
                max_guests = int(row.get('Max Guests', 1))
                kids_allowed = str(row.get('Kids Allowed', 'no')).lower() in ['true', '1', 'yes', 'si']
                max_kids = int(row.get('Max Kids', 0)) if kids_allowed else 0
                
                guest_data = {
                    'guest_name': guest_name,
                    'token': secrets.token_urlsafe(32),
                    'max_guests': max_guests,
                    'kids_allowed': kids_allowed,
                    'max_kids': max_kids,
                    'phone_number': normalized_phone,
                    'sent_by_admin_id': session.get('user_id')
                }
                supabase.from_('guests').insert(guest_data).execute()

            flash('Guests imported successfully from Excel file.', 'success')
        except Exception as e:
            current_app.logger.error(f"Error processing Excel file: {e}")
            flash(f'Error processing Excel file: {str(e)}', 'danger')
            
        return redirect(url_for('admin.manage_guests'))
    else:
        flash('Invalid file type. Please upload a .xlsx file.', 'danger')
        return redirect(url_for('admin.manage_guests'))

@bp.route('/guest/<int:guest_id>/update', methods=['POST'])
@login_required
def update_guest(guest_id):
    supabase = get_supabase_client()
    
    # Extract data from form
    guest_name = request.form.get('guest_name', '').strip()
    phone_number = request.form.get('phone_number', '').strip()
    max_guests = request.form.get('max_guests', 1, type=int)
    max_kids = request.form.get('max_kids', 0, type=int)
    kids_allowed = 'kids_allowed' in request.form
    
    if not guest_name:
        flash('Guest name cannot be empty.', 'danger')
        return redirect(url_for('admin.manage_guests'))
        
    try:
        # Sanitize phone number
        normalized_phone = sanitize_and_normalize_phone(phone_number) if phone_number else None
        
        # Prepare data for update
        update_data = {
            'guest_name': guest_name,
            'max_guests': max_guests,
            'kids_allowed': kids_allowed,
            'max_kids': max_kids if kids_allowed else 0,
            'phone_number': normalized_phone
        }
        
        # Execute update
        supabase.from_('guests').update(update_data).eq('id', guest_id).execute()
        
        flash(f'Guest "{guest_name}" has been updated successfully.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error updating guest {guest_id}: {e}")
        flash(f'An error occurred while updating the guest: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_guests'))

@bp.route('/guest/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete_guest(guest_id):
    supabase = get_supabase_client()
    try:
        # Optional: First, find the guest to get their name for the flash message
        guest_response = supabase.from_('guests').select('guest_name').eq('id', guest_id).execute()
        guest_name = guest_response.data[0]['guest_name'] if guest_response.data else f"ID {guest_id}"

        # Delete the guest
        supabase.from_('guests').delete().eq('id', guest_id).execute()
        
        flash(f'Guest "{guest_name}" has been deleted successfully.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error deleting guest {guest_id}: {e}")
        flash(f'An error occurred while deleting the guest: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_guests'))

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

@bp.route('/rsvp_dashboard')
@login_required
def rsvp_dashboard():
    supabase = get_supabase_client()
    
    total_invitations = 0
    answered_invitations = 0
    total_adults = 0
    total_children = 0
    not_attending_adults = 0
    not_attending_kids = 0
    
    try:
        # Get total number of invitations
        guest_response = supabase.from_('guests').select('id', count='exact').execute()
        total_invitations = guest_response.count
        
        # Get answered invitations
        rsvp_response = supabase.from_('rsvps').select('attending,guests,kids,guest_token').execute()
        
        answered_invitations = len(rsvp_response.data)
        
        # Calculate total adults and children from answered RSVPs
        for rsvp in rsvp_response.data:
            if rsvp['attending']:
                total_adults += rsvp['guests']
                total_children += rsvp['kids']
            else:
                not_attending_adults += rsvp['guests']
                not_attending_kids += rsvp['kids']
                
    except Exception as e:
        current_app.logger.error(f"Error fetching RSVP data: {e}")
        flash(f"Error loading RSVP data: {str(e)}", 'danger')

    # Fetch guest details for answered RSVPs
    answered_guests = []
    if rsvp_response and rsvp_response.data:
        guest_tokens = [rsvp['guest_token'] for rsvp in rsvp_response.data if rsvp['guest_token']]
        if guest_tokens:
            try:
                guest_details_response = supabase.from_('guests').select('*').in_('token', guest_tokens).execute()
                guest_details_map = {guest['token']: guest for guest in guest_details_response.data}
                
                for rsvp in rsvp_response.data:
                    guest_info = guest_details_map.get(rsvp['guest_token'])
                    if guest_info:
                        answered_guests.append({
                            'guest_name': guest_info['guest_name'],
                            'attending': rsvp['attending'],
                            'adults': rsvp['guests'],
                            'children': rsvp['kids']
                        })
            except Exception as e:
                current_app.logger.error(f"Error fetching guest details for answered RSVPs: {e}")

    return render_template('rsvp_dashboard.html',
                           total_invitations=total_invitations,
                           answered_invitations=answered_invitations,
                           total_adults=total_adults,
                           total_children=total_children,
                           not_attending_adults=not_attending_adults,
                           not_attending_kids=not_attending_kids,
                           answered_guests=answered_guests)

@bp.route('/rsvps/export')
@login_required
def export_rsvps():
    supabase = get_supabase_client()
    try:
        rsvp_response = supabase.from_('rsvps').select('*, guest:guests(guest_name)').execute()
        
        if not rsvp_response.data:
            flash('No RSVP data to export.', 'info')
            return redirect(url_for('admin.rsvp_dashboard'))

        df_data = []
        for rsvp in rsvp_response.data:
            guest_name = rsvp.get('guest', {}).get('guest_name', 'N/A') if rsvp.get('guest') else 'N/A'
            df_data.append({
                'Guest Name': guest_name,
                'Attending': 'Yes' if rsvp['attending'] else 'No',
                'Adults': rsvp['guests'],
                'Children': rsvp['kids'],
                'Dietary Restrictions': rsvp['dietary_restrictions'],
                'Submitted At': rsvp['created_at']
            })
        
        df = pd.DataFrame(df_data)
        
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='RSVPs')
        writer.close()
        output.seek(0)
        
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='rsvp_export.xlsx')

    except Exception as e:
        current_app.logger.error(f"Error exporting RSVPs: {e}")
        flash(f"Error exporting data: {str(e)}", 'danger')
        return redirect(url_for('admin.rsvp_dashboard'))