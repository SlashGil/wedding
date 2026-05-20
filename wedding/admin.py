import os
import secrets
import pandas as pd
from io import BytesIO
from urllib.parse import quote_plus
from datetime import datetime, timezone
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

def format_phone(phone_number):
    """Formats a phone number to separate country code if it has more than 10 digits."""
    if not phone_number or not phone_number.isdigit():
        return phone_number, ""
    
    if len(phone_number) > 10:
        country_code_len = len(phone_number) - 10
        country_code = f"+{phone_number[:country_code_len]}"
        local_number = phone_number[country_code_len:]
        return local_number, country_code
    
    return phone_number, ""

def generate_whatsapp_link(message, guest_name, invite_link, phone_number=None):
    """Generates a WhatsApp send link with a pre-filled message."""
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
            whatsapp_message = request.form.get('whatsapp_message', '').strip()
            set_setting('whatsapp_message', whatsapp_message)
            flash('Default WhatsApp message updated.')
            return redirect(url_for('admin.index'))
        
        if 'update_pinterest_links' in request.form:
            set_setting('pinterest_women', request.form.get('pinterest_women', '').strip())
            set_setting('pinterest_men', request.form.get('pinterest_men', '').strip())
            flash('Pinterest links updated successfully.')
            return redirect(url_for('admin.index'))

    rsvp_answers = []
    uploaded_photos = []

    try:
        rsvp_response = supabase.from_('rsvps').select(
            'id,name,attending,guests,kids,dietary_restrictions,created_at,invited_guest:guests(guest_name)'
        ).order('id', desc=True).execute()
        for rsvp in rsvp_response.data:
            invited_guest = rsvp.get('invited_guest') if isinstance(rsvp.get('invited_guest'), dict) else {}
            rsvp_answers.append({
                'id': rsvp.get('id'),
                'name': rsvp.get('name'),
                'attending': rsvp.get('attending'),
                'guests': rsvp.get('guests', 0),
                'kids': rsvp.get('kids', 0),
                'dietary_restrictions': rsvp.get('dietary_restrictions'),
                'created_at': rsvp.get('created_at'),
                'invite_name': invited_guest.get('guest_name') or 'N/A'
            })

        photo_response = supabase.from_('photos').select('id, filename, is_visible').order('id', desc=True).execute()
        
        if photo_response.data:
            photo_paths = [f"photos/{p['filename']}" for p in photo_response.data]
            
            transform_options = {'width': 200, 'height': 200, 'resize': 'cover'}
            signed_urls_response = supabase.storage.from_(bucket_name).create_signed_urls(photo_paths, 3600, options={'transform': transform_options})
            
            url_map = {os.path.basename(item['path']): item['signedURL'] for item in signed_urls_response if not item.get('error')}

            for photo_data in photo_response.data:
                filename = photo_data['filename']
                if filename in url_map:
                    uploaded_photos.append({
                        'id': photo_data['id'],
                        'filename': filename,
                        'url': url_map[filename],
                        'is_visible': photo_data.get('is_visible', True)
                    })

    except Exception as e:
        current_app.logger.error(f"Error fetching data from Supabase: {e}")
        flash(f"Error loading data: {str(e)}")

    current_hero_filename = get_setting('hero_image_filename')
    current_hero_url = None
    if current_hero_filename:
        try:
            transform_options = {'width': 600, 'quality': 75}
            signed_url_response = supabase.storage.from_(bucket_name).create_signed_url(f"uploads/{current_hero_filename}", 3600, options={'transform': transform_options})
            current_hero_url = signed_url_response['signedURL']
        except Exception as e:
            current_app.logger.error(f"Error fetching hero image URL from Supabase Storage: {e}")

    dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
    dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
    
    pinterest_links = {
        'women': get_setting('pinterest_women', ''),
        'men': get_setting('pinterest_men', '')
    }
    
    default_whatsapp_message = get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}')

    return render_template('admin.html', rsvp_answers=rsvp_answers, uploaded_photos=uploaded_photos, current_hero_url=current_hero_url, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links, whatsapp_message=default_whatsapp_message)

@bp.route('/rsvps/export')
@login_required
def export_rsvps():
    supabase = get_supabase_client()
    try:
        response = supabase.from_('rsvps').select(
            'name,kids,dietary_restrictions,created_at,guests,invited_guest:guests(guest_name, phone_number)'
        ).eq('attending', True).order('id').execute()
        
        if not response.data:
            flash('No confirmed guests to export.')
            return redirect(url_for('admin.index'))

        export_data = []
        for rsvp in response.data:
            invited_guest = rsvp.get('invited_guest') if isinstance(rsvp.get('invited_guest'), dict) else {}
            export_data.append({
                'RSVP Name': rsvp.get('name'),
                'Original Invite For': invited_guest.get('guest_name') or 'Public Form',
                'Phone Number': invited_guest.get('phone_number') or '',
                'Confirmed Adults': rsvp.get('guests', 0),
                'Confirmed Kids': rsvp.get('kids', 0),
                'Dietary Restrictions': rsvp.get('dietary_restrictions'),
                'Submission Date': rsvp.get('created_at')
            })

        df = pd.DataFrame(export_data)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Confirmed Guests')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='confirmed_guests.xlsx'
        )

    except Exception as e:
        current_app.logger.error(f"Error exporting RSVPs: {e}")
        flash('An error occurred while exporting the guest list.')
        return redirect(url_for('admin.index'))

@bp.route('/users')
@login_required
def manage_users():
    supabase = get_supabase_client()
    users = []
    try:
        response = supabase.from_('admins').select('id, username, created_at').order('id').execute()
        users = response.data
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}")
        flash('Error loading admin users.')
        
    return render_template('users.html', users=users)

@bp.route('/users/new', methods=('GET', 'POST'))
@login_required
def new_user():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('admin.new_user'))
            
        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('admin.new_user'))
            
        supabase = get_supabase_client()
        try:
            existing = supabase.from_('admins').select('id').eq('username', username).execute()
            if existing.data:
                flash(f'User {username} already exists.')
                return redirect(url_for('admin.new_user'))
                
            supabase.from_('admins').insert({
                'username': username,
                'password_hash': generate_password_hash(password)
            }).execute()
            
            flash(f'Admin user {username} created successfully.')
            return redirect(url_for('admin.manage_users'))
            
        except Exception as e:
            current_app.logger.error(f"Error creating user: {e}")
            flash('An error occurred while creating the user.')
            
    return render_template('new_user.html')

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('user_id') == user_id:
         flash('You cannot delete your own account while logged in.')
         return redirect(url_for('admin.manage_users'))
         
    supabase = get_supabase_client()
    try:
        user_response = supabase.from_('admins').select('username').eq('id', user_id).execute()
        if not user_response.data:
             flash('User not found.')
             return redirect(url_for('admin.manage_users'))
             
        username = user_response.data[0]['username']
        supabase.from_('admins').delete().eq('id', user_id).execute()
        flash(f'Admin user {username} deleted successfully.')
    except Exception as e:
        current_app.logger.error(f"Error deleting user: {e}")
        flash('An error occurred while deleting the user.')
        
    return redirect(url_for('admin.manage_users'))

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
            phone, code = format_phone(guest.get('phone_number'))
            guest['phone_number_formatted'] = phone
            guest['country_code'] = code
            
            admin = guest.get('sent_by_admin')
            guest['sent_by_username'] = admin['username'] if isinstance(admin, dict) else None

    except Exception as e:
        current_app.logger.error(f"Error fetching guests from Supabase: {e}")
        flash(f"Error loading guests: {str(e)}")
        
    return render_template('guests.html', 
                           guest_links=guest_links, 
                           whatsapp_message=whatsapp_message,
                           total_invitations=total_invitations,
                           total_guests=total_guests,
                           total_kids=total_kids)

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
    if request.method == 'POST':
        supabase = get_supabase_client()
        guest_name = request.form.get('guest_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        max_guests = request.form.get('max_guests', '1').strip()
        kids_allowed = request.form.get('kids_allowed') == 'on'
        max_kids = request.form.get('max_kids', '0').strip()

        if not guest_name:
            flash('Guest name is required.')
            return redirect(url_for('admin.new_guest'))

        try:
            max_guests_int = max(1, int(max_guests))
            max_kids_int = max(0, int(max_kids))
        except ValueError:
            flash('Max guests and max kids must be valid numbers.')
            return redirect(url_for('admin.new_guest'))

        if not kids_allowed: max_kids_int = 0
        token = secrets.token_urlsafe(10)

        try:
            supabase.from_('guests').insert({
                'guest_name': guest_name,
                'phone_number': phone_number,
                'max_guests': max_guests_int,
                'kids_allowed': kids_allowed,
                'max_kids': max_kids_int,
                'token': token
            }).execute()
            
            invite_link = url_for('main.invite', token=token, _external=True)
            whatsapp_message = get_setting('whatsapp_message', 'Hello {guest_name}, you are invited to our wedding! You can confirm your attendance here: {invite_link}')
            
            session['new_invite_info'] = {
                'guest_name': guest_name,
                'invite_link': invite_link,
                'whatsapp_link': generate_whatsapp_link(whatsapp_message, guest_name, invite_link, phone_number)
            }
            flash(f'Invite created for {guest_name}.')
        except Exception as e:
            current_app.logger.error(f"Error creating guest in Supabase: {e}")
            flash(f'Error creating guest: {str(e)}')
        
        return redirect(url_for('admin.manage_guests'))
    
    new_invite_info = session.pop('new_invite_info', None)
    return render_template('new_guest.html', new_invite_info=new_invite_info)


@bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    supabase = get_supabase_client()
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('admin.manage_guests'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('admin.manage_guests'))
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            df = pd.read_excel(file)
            required_cols = ['Name', 'Max Guests']
            if not all(col in df.columns for col in required_cols):
                flash(f'Missing required columns: {", ".join(required_cols)}')
                return redirect(url_for('admin.manage_guests'))

            guests_to_insert = []
            for _, row in df.iterrows():
                guest_name = str(row['Name']).strip()
                if not guest_name or guest_name == 'nan': continue
                try: max_guests = max(1, int(row['Max Guests']))
                except (ValueError, TypeError): max_guests = 1
                kids_allowed = str(row.get('Kids Allowed', 'no')).strip().lower() in ['yes', 'true', '1', 'y']
                max_kids = 0
                if kids_allowed:
                    try: max_kids = max(0, int(row.get('Max Kids', 0)))
                    except (ValueError, TypeError): max_kids = 0
                phone_number = str(row.get('Phone Number', '')).strip()
                token = secrets.token_urlsafe(10)
                guests_to_insert.append({
                    'guest_name': guest_name,
                    'phone_number': phone_number,
                    'max_guests': max_guests,
                    'kids_allowed': kids_allowed,
                    'max_kids': max_kids,
                    'token': token
                })
            
            if guests_to_insert:
                supabase.from_('guests').insert(guests_to_insert).execute()
            flash(f'Successfully imported {len(guests_to_insert)} guests from {file.filename}.')
        except Exception as e:
            current_app.logger.error(f"Error processing Excel file or inserting guests: {e}")
            flash(f'Error processing file: {str(e)}')
    else:
        flash('Invalid file format. Please upload an Excel file (.xlsx or .xls).')
    return redirect(url_for('admin.manage_guests'))


@bp.route('/guest/<int:guest_id>/update', methods=['POST'])
@login_required
def update_guest(guest_id):
    supabase = get_supabase_client()
    guest_name = request.form.get('guest_name', '').strip()
    phone_number = request.form.get('phone_number', '').strip()
    max_guests = request.form.get('max_guests', '1').strip()
    kids_allowed = request.form.get('kids_allowed') == 'on'
    max_kids = request.form.get('max_kids', '0').strip()
    is_attending = request.form.get('is_attending') == 'on'

    if not guest_name:
        flash('Guest name is required to update an invite.')
        return redirect(url_for('admin.manage_guests'))

    try:
        max_guests_int = max(1, int(max_guests))
        max_kids_int = max(0, int(max_kids))
    except ValueError:
        flash('Max guests and max kids must be valid numbers.')
        return redirect(url_for('admin.manage_guests'))

    if not kids_allowed: max_kids_int = 0

    try:
        supabase.from_('guests').update({
            'guest_name': guest_name,
            'phone_number': phone_number,
            'max_guests': max_guests_int,
            'kids_allowed': kids_allowed,
            'max_kids': max_kids_int,
            'is_attending': is_attending
        }).eq('id', guest_id).execute()
        flash(f'Invite updated for {guest_name}.')
    except Exception as e:
        current_app.logger.error(f"Error updating guest in Supabase: {e}")
        flash(f'Error updating guest: {str(e)}')
    return redirect(url_for('admin.manage_guests'))


@bp.route('/guest/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete_guest(guest_id):
    supabase = get_supabase_client()
    try:
        guest_response = supabase.from_('guests').select('guest_name, token').eq('id', guest_id).execute()
        guest_data = guest_response.data[0] if guest_response.data else None

        if not guest_data:
            flash('Guest invite not found.')
            return redirect(url_for('admin.manage_guests'))
        
        if guest_data['token']:
            supabase.from_('rsvps').delete().eq('guest_token', guest_data['token']).execute()
        
        supabase.from_('guests').delete().eq('id', guest_id).execute()
        flash(f"Invite deleted for {guest_data['guest_name']}.")
    except Exception as e:
        current_app.logger.error(f"Error deleting guest or RSVPs from Supabase: {e}")
        flash(f"Error deleting invite: {str(e)}")
    return redirect(url_for('admin.manage_guests'))


@bp.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']

    if 'photo' not in request.files or request.files['photo'].filename == '':
        flash('No selected file')
        return redirect(url_for('admin.index'))

    file = request.files['photo']
    if not file or not allowed_file(file.filename):
        flash(f'Invalid file type. Allowed types are: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}.')
        return redirect(url_for('admin.index'))

    filename = secure_filename(file.filename)
    file_content = file.read()
    path_on_storage = f"photos/{filename}"
    
    inserted_id = None
    try:
        # First, insert a record into the database.
        response = supabase.from_('photos').insert({'filename': filename, 'is_visible': True}).execute()
        if not response.data:
            raise Exception("Database insert failed. Check RLS policies on 'photos' table.")
        
        inserted_id = response.data[0]['id']

        # If DB insert is successful, upload the file to storage.
        supabase.storage.from_(bucket_name).upload(path_on_storage, file_content, {'content-type': file.content_type})
        
        flash(f'Photo "{filename}" uploaded successfully.')

    except Exception as e:
        # If anything fails, log the error and flash a message.
        current_app.logger.error(f"Error uploading photo: {e}")
        flash(f'An error occurred: {str(e)}')
        
        # If the database record was created but the upload failed, roll back the DB insert.
        if inserted_id:
            try:
                supabase.from_('photos').delete().eq('id', inserted_id).execute()
                current_app.logger.info(f"Rolled back photo insert for id {inserted_id}")
            except Exception as rollback_e:
                current_app.logger.error(f"Fatal: Failed to roll back photo insert: {rollback_e}")

    return redirect(url_for('admin.index'))


@bp.route('/photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']

    if not photo_id:
        flash('Photo ID is missing.')
        return redirect(url_for('admin.index'))

    try:
        photo_response = supabase.from_('photos').select('filename').eq('id', photo_id).execute()
        photo_data = photo_response.data[0] if photo_response.data else None

        if not photo_data:
            flash('Photo not found.')
            return redirect(url_for('admin.index'))
        
        filename = photo_data['filename']
        path_on_storage = f"photos/{filename}"

        supabase.storage.from_(bucket_name).remove([path_on_storage])
        
        supabase.from_('photos').delete().eq('id', photo_id).execute()
        flash(f"Photo '{filename}' deleted successfully.")
    except Exception as e:
        current_app.logger.error(f"Error deleting photo from Supabase: {e}")
        flash(f"Error deleting photo: {str(e)}")
    return redirect(url_for('admin.index'))


@bp.route('/photo/<int:photo_id>/toggle_visibility', methods=['POST'])
@login_required
def toggle_photo_visibility(photo_id):
    supabase = get_supabase_client()
    try:
        # First, get the current visibility status
        photo_response = supabase.from_('photos').select('is_visible').eq('id', photo_id).execute()
        if not photo_response.data:
            flash('Photo not found.')
            return redirect(url_for('admin.index'))
        
        current_visibility = photo_response.data[0].get('is_visible', True)
        new_visibility = not current_visibility
        
        # Update the visibility in the database
        supabase.from_('photos').update({'is_visible': new_visibility}).eq('id', photo_id).execute()
        
        status = "shown" if new_visibility else "hidden"
        flash(f'Photo visibility updated. It is now {status}.')
        
    except Exception as e:
        current_app.logger.error(f"Error toggling photo visibility: {e}")
        flash(f'An error occurred: {str(e)}')

    return redirect(url_for('admin.index'))


@bp.route('/upload_hero', methods=['POST'])
@login_required
def upload_hero():
    supabase = get_supabase_client()
    bucket_name = current_app.config['SUPABASE_BUCKET']

    if 'hero_image' not in request.files or request.files['hero_image'].filename == '':
        flash('No file selected for hero image.')
        return redirect(url_for('admin.index'))

    file = request.files['hero_image']
    if not file or not allowed_file(file.filename):
        flash(f'Invalid file type for hero image. Allowed: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}.')
        return redirect(url_for('admin.index'))

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"hero_{secrets.token_hex(8)}.{ext}"
    path_on_storage = f"uploads/{filename}"
    
    try:
        # Step 1: Upload the new file.
        supabase.storage.from_(bucket_name).upload(path_on_storage, file.read(), {'content-type': file.content_type})

        # Step 2: If upload is successful, update the database.
        old_filename = get_setting('hero_image_filename')
        set_setting('hero_image_filename', filename)
        flash('Hero image updated successfully.')

        # Step 3: If database update is successful, delete the old file.
        if old_filename and old_filename != filename:
            try:
                old_path_on_storage = f"uploads/{old_filename}"
                supabase.storage.from_(bucket_name).remove([old_path_on_storage])
            except Exception as e:
                current_app.logger.error(f"Non-fatal: Failed to remove old hero image '{old_filename}': {e}")

    except Exception as e:
        # If any step fails, log the error and attempt to roll back the file upload.
        current_app.logger.error(f"Error updating hero image: {e}")
        flash(f'An error occurred while updating hero image: {str(e)}')
        try:
            supabase.storage.from_(bucket_name).remove([path_on_storage])
            current_app.logger.info(f"Rolled back hero image upload for '{filename}'")
        except Exception as rollback_e:
            current_app.logger.error(f"Fatal: Failed to roll back hero image upload: {rollback_e}")

    return redirect(url_for('admin.index'))