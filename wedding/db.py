from flask import current_app, g
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


def init_app(app):
    # No specific teardown needed for Supabase client in this pattern,
    # as it's stateless per request.
    pass
