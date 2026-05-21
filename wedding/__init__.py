import os
from flask import Flask, current_app
from datetime import datetime

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, 
                instance_relative_config=True,
                template_folder='templates',
                static_folder='static')

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY'),
        ADMIN_USERNAME=os.environ.get('WEDDING_ADMIN_USERNAME', 'admin'),
        ADMIN_PASSWORD=os.environ.get('WEDDING_ADMIN_PASSWORD', 'wedding2026'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
        SUPABASE_URL=os.environ.get('SUPABASE_URL'),
        SUPABASE_KEY=os.environ.get('SUPABASE_KEY'),
        SUPABASE_BUCKET='wedding-images',
        GALLERY_FALLBACK_URLS=[
            'https://images.unsplash.com/photo-1515934751635-c81c6bc9a2d8?auto=format&fit=crop&w=800&q=60',
            'https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=800&q=60',
            'https://images.unsplash.com/photo-1500964757637-c85e8a162699?auto=format&fit=crop&w=800&q=60',
            'https://images.unsplash.com/photo-1485899991321-205b3f7a41e4?auto=format&fit=crop&w=800&q=60',
            'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=800&q=60',
            'https://images.unsplash.com/photo-1522673607200-164d1b6ce486?auto=format&fit=crop&w=800&q=60',
        ]
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'css'), exist_ok=True)
    except OSError:
        pass

    from . import db
    db.init_app(app)

    from . import auth, main_routes, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(admin.bp)

    app.add_url_rule('/', endpoint='index')

    @app.template_filter('format_datetime')
    def format_datetime(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        # Supabase returns ISO 8601 format with TZ info
        if isinstance(value, str):
            try:
                # Handle the +00:00 timezone format
                if '+' in value:
                    value = value.split('+')[0]
                dt = datetime.fromisoformat(value)
                return dt.strftime(format)
            except (ValueError, TypeError):
                return value
        return value

    @app.context_processor
    def inject_hero_image():
        from .db import get_setting, get_supabase_client
        supabase = get_supabase_client()
        bucket_name = current_app.config['SUPABASE_BUCKET']
        hero_filename = get_setting('hero_image_filename')
        hero_image_url = 'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=1920&q=80'
        if hero_filename:
            try:
                # Use signed URL with transformation for public hero image
                transform_options = {'width': 1920, 'height': 1080, 'quality': 80, 'resize': 'cover'}
                signed_url_response = supabase.storage.from_(bucket_name).create_signed_url(f"uploads/{hero_filename}", 3600, options={'transform': transform_options})
                hero_image_url = signed_url_response['signedURL']
            except Exception as e:
                app.logger.error(f"Error fetching hero image from Supabase Storage: {e}")
        return dict(hero_image_url=hero_image_url)

    @app.context_processor
    def inject_photos():
        from .db import get_supabase_client
        supabase = get_supabase_client()
        bucket_name = current_app.config['SUPABASE_BUCKET']

        photos = []
        try:
            response = supabase.from_('photos').select('filename').eq('is_visible', True).order('created_at', desc=True).execute()
            
            if response.data:
                photo_files = [p['filename'] for p in response.data if p.get('filename')]
                
                if photo_files:
                    # Generate Thumbnail URLs
                    thumb_paths = [f"photos/{name}" for name in photo_files]
                    thumb_transform = {'width': 400, 'height': 400, 'resize': 'cover', 'quality': 75}
                    thumb_urls_res = supabase.storage.from_(bucket_name).create_signed_urls(thumb_paths, 3600, options={'transform': thumb_transform})
                    thumb_map = {os.path.basename(item['path']): item['signedURL'] for item in thumb_urls_res if not item.get('error')}

                    # Generate Full-size Image URLs
                    full_paths = [f"photos/{name}" for name in photo_files]
                    full_transform = {'width': 1920, 'height': 1080, 'quality': 85}
                    full_urls_res = supabase.storage.from_(bucket_name).create_signed_urls(full_paths, 3600, options={'transform': full_transform})
                    full_map = {os.path.basename(item['path']): item['signedURL'] for item in full_urls_res if not item.get('error')}

                    for filename in photo_files:
                        if filename in thumb_map and filename in full_map:
                            photos.append({
                                'thumbnail': thumb_map[filename],
                                'full': full_map[filename],
                                'filename': filename
                            })

        except Exception as e:
            app.logger.error(f"Error fetching photos from Supabase: {e}")

        if not photos:
            fallback_urls = app.config['GALLERY_FALLBACK_URLS']
            for i, url in enumerate(fallback_urls):
                photos.append({'thumbnail': url, 'full': url, 'filename': f'fallback_{i+1}.jpg'})

        return dict(photos=photos)

    return app