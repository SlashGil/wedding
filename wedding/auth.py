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
                is_master_user = (
                    username == current_app.config['ADMIN_USERNAME'] and
                    password == current_app.config['ADMIN_PASSWORD']
                )
                if is_master_user:
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


@bp.route('/forgot_password', methods=('GET', 'POST'))
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()

        if not username:
            flash('Username is required.', 'danger')
            return render_template('forgot_password.html')

        try:
            supabase = get_supabase_client()
            user_response = supabase.from_('admins').select('id, username').eq('username', username).single().execute()
            user = user_response.data

            if user:
                # In a real app, you'd email a reset link.
                # For this internal tool, we'll just redirect to a password reset page.
                return redirect(url_for('auth.reset_password', user_id=user['id']))
            else:
                flash('Username not found.', 'danger')

        except Exception as e:
            current_app.logger.error(f"Error in forgot password: {e}")
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('forgot_password.html')


@bp.route('/reset_password/<int:user_id>', methods=('GET', 'POST'))
def reset_password(user_id):
    supabase = get_supabase_client()

    try:
        user_response = supabase.from_('admins').select('id, username').eq('id', user_id).single().execute()
        user = user_response.data
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f"Error fetching user: {e}")
        flash(f"Error fetching user: {str(e)}", 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password', '').strip()

        if not password:
            flash('Password is required.', 'danger')
            return render_template('reset_password.html', user=user)

        try:
            hashed_password = generate_password_hash(password)
            supabase.from_('admins').update({
                'password_hash': hashed_password
            }).eq('id', user_id).execute()
            flash(f'Password for user "{user["username"]}" has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            current_app.logger.error(f"Error resetting password: {e}")
            flash(f'Error resetting password: {str(e)}', 'danger')

    return render_template('reset_password.html', user=user)


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