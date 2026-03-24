import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def ensure_column(conn, table_name, column_name, definition):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {col['name'] for col in columns}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_db():
    db = get_db()
    # This is a non-destructive init, it only creates tables if they don't exist
    db.execute('CREATE TABLE IF NOT EXISTS guests (id INTEGER PRIMARY KEY, guest_name TEXT NOT NULL, max_guests INTEGER NOT NULL DEFAULT 1, kids_allowed BOOLEAN NOT NULL DEFAULT 0, max_kids INTEGER NOT NULL DEFAULT 0, token TEXT NOT NULL UNIQUE, phone TEXT, preferred_lang TEXT DEFAULT "es", whatsapp_message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS rsvps (id INTEGER PRIMARY KEY, name TEXT NOT NULL, attending BOOLEAN NOT NULL, guests INTEGER NOT NULL, kids INTEGER NOT NULL DEFAULT 0, dietary_restrictions TEXT, guest_token TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY, filename TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')

    # Lightweight migration for older database versions
    ensure_column(db, 'rsvps', 'kids', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(db, 'rsvps', 'guest_token', 'TEXT')
    ensure_column(db, 'rsvps', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ensure_column(db, 'guests', 'phone', 'TEXT')
    ensure_column(db, 'guests', 'preferred_lang', 'TEXT DEFAULT "es"')
    ensure_column(db, 'guests', 'whatsapp_message', 'TEXT')


def get_setting(key, default=None):
    db = get_db()
    row = db.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    # Register the close_db function to be called after each request
    app.teardown_appcontext(close_db)
    # Add the new 'init-db' command to the flask CLI
    app.cli.add_command(init_db_command)