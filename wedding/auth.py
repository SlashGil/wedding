import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash

bp = Blueprint('auth', __name__, url_prefix='/admin')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('admin.index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None

        if username != current_app.config['ADMIN_USERNAME'] or not check_password_hash(current_app.config['ADMIN_PASSWORD'], password):
            # For production, it's better to hash the password from the env var on app start
            # For simplicity here, we'll compare plain text from env with a hashed version if needed, or just plain text
            if username != current_app.config['ADMIN_USERNAME'] or password != current_app.config['ADMIN_PASSWORD']:
                 error = 'Invalid username or password.'

        if error is None:
            session.clear()
            session['user_id'] = 1 # A simple user ID for the admin
            return redirect(url_for('admin.index'))

        flash(error)

    return render_template('admin_login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = {'id': user_id} if user_id is not None else None

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