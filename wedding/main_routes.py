from flask import (
    Blueprint, flash, redirect, render_template, request, url_for, current_app
)
from .db import get_supabase_client, get_setting

bp = Blueprint('main', __name__)


@bp.route('/')
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

    dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
    dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
    
    pinterest_links = {
        'women': get_setting('pinterest_women', ''),
        'men': get_setting('pinterest_men', '')
    }
    
    # hero_image_url is now provided by the inject_hero_image context processor
    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links)


@bp.route('/invite/<token>')
def invite(token):
    supabase = get_supabase_client()
    try:
        response = supabase.from_('guests').select('*').eq('token', token).execute()
        guest_data = response.data[0] if response.data else None
    except Exception as e:
        current_app.logger.error(f"Error fetching guest from Supabase: {e}")
        guest_data = None

    if not guest_data:
        flash('This invite link is invalid. Please contact the couple.')
        return redirect(url_for('main.index'))

    guest = {
        'token': guest_data.get('token'),
        'guest_name': guest_data.get('guest_name'),
        'max_guests': guest_data.get('max_guests', 1),
        'kids_allowed': guest_data.get('kids_allowed', False),
        'max_kids': guest_data.get('max_kids', 0),
        'is_attending': guest_data.get('is_attending', False)
    }

    dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
    dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
    
    pinterest_links = {
        'women': get_setting('pinterest_women', ''),
        'men': get_setting('pinterest_men', '')
    }
    
    # hero_image_url is now provided by the inject_hero_image context processor
    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links)


@bp.route('/rsvp', methods=['POST'])
def rsvp():
    supabase = get_supabase_client()
    token = request.form.get('guest_token', '').strip()
    name = request.form.get('name', '').strip()
    attending = request.form.get('attending') == 'yes'

    if not name:
        flash('Please enter your name.')
        return redirect(request.referrer or url_for('main.index'))

    guest_data = None
    if token:
        try:
            response = supabase.from_('guests').select('*').eq('token', token).execute()
            guest_data = response.data[0] if response.data else None
        except Exception as e:
            current_app.logger.error(f"Error fetching guest for RSVP from Supabase: {e}")

    max_guests = int(guest_data.get('max_guests')) if guest_data else 10
    kids_allowed = bool(guest_data.get('kids_allowed')) if guest_data else False
    max_kids = int(guest_data.get('max_kids')) if guest_data else 0

    try:
        guests = int(request.form.get('guests', 1))
        kids = int(request.form.get('kids', 0))
    except ValueError:
        flash('Please provide valid numbers for guests and kids.')
        return redirect(request.referrer or url_for('main.index'))

    if guests < 1: guests = 1
    if guests > max_guests: guests = max_guests
    if kids < 0: kids = 0
    if not kids_allowed:
        kids = 0
    elif kids > max_kids:
        kids = max_kids

    dietary = request.form.get('dietary_restrictions', '').strip()

    try:
        supabase.from_('rsvps').upsert({
            'name': name,
            'attending': attending,
            'guests': guests,
            'kids': kids,
            'dietary_restrictions': dietary,
            'guest_token': token if token else None
        }).execute()
    except Exception as e:
        current_app.logger.error(f"Error inserting RSVP into Supabase: {e}")
        flash('There was an error submitting your RSVP. Please try again.')
        return redirect(request.referrer or url_for('main.index'))

    if token:
        try:
            supabase.from_('guests').update({'is_attending': attending}).eq('token', token).execute()
            if guest_data:
                guest_data['is_attending'] = attending
        except Exception as e:
            current_app.logger.error(f"Error updating guest is_attending status: {e}")

    if guest_data:
        submitted_data = {
            'name': name,
            'attending': attending,
            'guests': guests,
            'kids': kids,
            'kids_allowed': kids_allowed,
        }
        dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
        dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
        
        pinterest_links = {
            'women': get_setting('pinterest_women', ''),
            'men': get_setting('pinterest_men', '')
        }
        
        # hero_image_url is now provided by the inject_hero_image context processor
        return render_template('index.html', guest=guest_data, rsvp_submitted=True, submitted_data=submitted_data, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links)

    flash('Thank you for your RSVP!')
    return redirect(url_for('main.index', name=name, guests=guests))

@bp.route('/guest/manage', methods=('GET', 'POST'))
def manage_guest():
    token = request.args.get('token')
    if not token:
        flash('No invitation token provided.')
        return redirect(url_for('main.index'))

    supabase = get_supabase_client()
    try:
        response = supabase.from_('guests').select('*').eq('token', token).execute()
        guest_data = response.data[0] if response.data else None
    except Exception as e:
        current_app.logger.error(f"Error fetching guest from Supabase: {e}")
        guest_data = None

    if not guest_data:
        flash('This invite link is invalid. Please contact the couple.')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        max_guests = int(request.form.get('max_guests', 1))
        max_kids = int(request.form.get('max_kids', 0))

        try:
            supabase.from_('guests').update({
                'guest_name': guest_name,
                'max_guests': max_guests,
                'max_kids': max_kids
            }).eq('token', token).execute()
            flash('Your invitation details have been updated.', 'success')
        except Exception as e:
            current_app.logger.error(f"Error updating guest details: {e}")
            flash('There was an error updating your invitation. Please try again.', 'danger')
        return redirect(url_for('main.manage_guest', token=token))

    return render_template('manage_guest.html', guest=guest_data)

@bp.route('/guest/responses')
def guest_responses():
    token = request.args.get('token')
    if not token:
        flash('No invitation token provided.')
        return redirect(url_for('main.index'))

    supabase = get_supabase_client()
    try:
        response = supabase.from_('rsvps').select('*').eq('guest_token', token).execute()
        rsvp_answers = response.data
    except Exception as e:
        current_app.logger.error(f"Error fetching rsvps from Supabase: {e}")
        rsvp_answers = []

    return render_template('guest_responses.html', rsvp_answers=rsvp_answers)