import click
from flask import current_app, g
from flask.cli import with_appcontext
from supabase import create_client, Client


def get_supabase_client() -> Client:
    if 'supabase' not in g:
        supabase_url = current_app.config.get('SUPABASE_URL')
        supabase_key = current_app.config.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and Key must be configured in environment variables.")
        g.supabase = create_client(supabase_url, supabase_key)
    return g.supabase


def get_setting(key, default=None):
    supabase = get_supabase_client()
    try:
        response = supabase.from_('settings').select('value').eq('key', key).execute()
        if response.data:
            return response.data[0]['value']
        return default
    except Exception as e:
        current_app.logger.error(f"Error fetching setting from Supabase: {e}")
        return default


def set_setting(key, value):
    supabase = get_supabase_client()
    try:
        # Check if the setting exists
        response = supabase.from_('settings').select('key').eq('key', key).execute()
        if response.data:
            # Update existing setting
            supabase.from_('settings').update({'value': value}).eq('key', key).execute()
        else:
            # Insert new setting
            supabase.from_('settings').insert({'key': key, 'value': value}).execute()
    except Exception as e:
        current_app.logger.error(f"Error setting value in Supabase: {e}")


def get_db_schema():
    return """
-- SQL script to create all tables for the Wedding Site project

-- Table to store guest information and their unique invite tokens.
CREATE TABLE guests (
    id SERIAL PRIMARY KEY,
    guest_name TEXT NOT NULL,
    max_guests INTEGER NOT NULL DEFAULT 1,
    kids_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    max_kids INTEGER NOT NULL DEFAULT 0,
    token TEXT NOT NULL UNIQUE,
    is_attending BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store RSVP submissions from guests.
CREATE TABLE rsvps (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    attending BOOLEAN NOT NULL,
    guests INTEGER NOT NULL,
    kids INTEGER NOT NULL DEFAULT 0,
    dietary_restrictions TEXT,
    guest_token TEXT, -- This can optionally be a foreign key referencing guests(token)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table to store the filenames of uploaded gallery photos.
CREATE TABLE photos (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- A key-value store for various application settings like dress code, hero image, etc.
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Table to store admin user accounts for accessing the admin panel.
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Optional: Add a foreign key constraint to link RSVPs to guests for data integrity.
/*
ALTER TABLE rsvps
ADD CONSTRAINT fk_guest_token
FOREIGN KEY (guest_token)
REFERENCES guests(token)
ON DELETE SET NULL;
*/

-- Grant usage on the new sequences to the anon and authenticated roles
GRANT USAGE, SELECT ON SEQUENCE guests_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE rsvps_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE photos_id_seq TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE admins_id_seq TO anon, authenticated;
"""

@click.command('init-db')
def init_db_command():
    """Prints the SQL schema to initialize the Supabase database."""
    click.echo("--------------------------------------------------")
    click.echo("Copy and paste the following SQL script into your Supabase project's SQL Editor to initialize the database.")
    click.echo("You can find the SQL Editor at: Project Home -> SQL Editor -> New query")
    click.echo("--------------------------------------------------\n")
    click.echo(get_db_schema())
    click.echo("\n--------------------------------------------------")
    click.echo("After running the script, remember to set up Row Level Security (RLS) policies for each table.")
    click.echo("--------------------------------------------------")


def init_app(app):
    # Register the new 'init-db' command with the flask CLI
    app.cli.add_command(init_db_command)
    # No specific teardown needed for Supabase client in this pattern,
    # as it's stateless per request.
    pass
