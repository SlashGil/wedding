from flask import (
    Blueprint, flash, redirect, render_template, request, url_for
)
from .db import get_db, get_setting

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
    
    current_hero_filename = get_setting('hero_image_filename')
    hero_image_url = url_for('static', filename='uploads/' + current_hero_filename) if current_hero_filename else url_for('static', filename='img/default_hero.jpg')

    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links, hero_image_url=hero_image_url)


@bp.route('/invite/<token>')
def invite(token):
    with get_db() as conn:
        guest = conn.execute('SELECT * FROM guests WHERE token = ?', (token,)).fetchone()

    if not guest:
        flash('This invite link is invalid. Please contact the couple.')
        return redirect(url_for('main.index'))

    dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
    dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
    
    pinterest_links = {
        'women': get_setting('pinterest_women', ''),
        'men': get_setting('pinterest_men', '')
    }
    
    current_hero_filename = get_setting('hero_image_filename')
    hero_image_url = url_for('static', filename='uploads/' + current_hero_filename) if current_hero_filename else url_for('static', filename='img/default_hero.jpg')

    return render_template('index.html', guest=guest, rsvp_submitted=False, submitted_data=None, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links, hero_image_url=hero_image_url)


@bp.route('/rsvp', methods=['POST'])
def rsvp():
    token = request.form.get('guest_token', '').strip()
    name = request.form.get('name', '').strip()
    attending = request.form.get('attending') == 'yes'

    if not name:
        flash('Please enter your name.')
        return redirect(request.referrer or url_for('main.index'))

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
            return redirect(request.referrer or url_for('main.index'))

        if guests < 1: guests = 1
        if guests > max_guests: guests = max_guests
        if kids < 0: kids = 0
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
        dress_code_es = get_setting('dress_code_es', 'Formal / Etiqueta Opcional')
        dress_code_en = get_setting('dress_code_en', 'Formal / Black-Tie Optional')
        
        pinterest_links = {
            'women': get_setting('pinterest_women', ''),
            'men': get_setting('pinterest_men', '')
        }
        
        current_hero_filename = get_setting('hero_image_filename')
        hero_image_url = url_for('static', filename='uploads/' + current_hero_filename) if current_hero_filename else url_for('static', filename='img/default_hero.jpg')

        return render_template('index.html', guest=guest, rsvp_submitted=True, submitted_data=submitted_data, dress_code_es=dress_code_es, dress_code_en=dress_code_en, pinterest_links=pinterest_links, hero_image_url=hero_image_url)

    flash('Thank you for your RSVP!')
    return redirect(url_for('main.index', name=name, guests=guests))