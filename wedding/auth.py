import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_supabase_client

bp = Blueprint('auth', __name__, url_prefix='/admin')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('admin.index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        supabase = get_supabase_client()

        try:
            # Check database for admin user
            response = supabase.from_('admins').select('*').eq('username', username).execute()
            admin_data = response.data[0] if response.data else None

            if admin_data:
                if not check_password_hash(admin_data['password_hash'], password):
                    error = 'Invalid username or password.'
                else:
                    session.clear()
                    session['user_id'] = admin_data['id']
                    session['username'] = admin_data['username']
                    return redirect(url_for('admin.index'))
            else:
                # Fallback to env vars for the initial master admin
                if username == current_app.config['ADMIN_USERNAME'] and password == current_app.config['ADMIN_PASSWORD']:
                    session.clear()
                    session['user_id'] = 'master'
                    session['username'] = username
                    return redirect(url_for('admin.index'))
                else:
                    error = 'Invalid username or password.'
        except Exception as e:
            current_app.logger.error(f"Error during login: {e}")
            error = 'An error occurred during login. Make sure your database is configured.'

        if error:
            flash(error)

    return render_template('admin_login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = {'id': user_id, 'username': session.get('username')} if user_id is not None else None

@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view
