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
        CLOUDFLARE_DOMAIN='media.caritoychava.lat', # Your new Cloudflare subdomain
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
        if isinstance(value, str):
            try:
                if '+' in value:
                    value = value.split('+')[0]
                dt = datetime.fromisoformat(value)
                return dt.strftime(format)
            except (ValueError, TypeError):
                return value
        return value

    def get_image_url(path, transform_params):
        base_url = f"https://{current_app.config['CLOUDFLARE_DOMAIN']}/{current_app.config['SUPABASE_BUCKET']}/{path}"
        params = '&'.join([f'{k}={v}' for k, v in transform_params.items()])
        return f"{base_url}?{params}"

    @app.context_processor
    def inject_hero_image():
        from .db import get_setting
        hero_filename = get_setting('hero_image_filename')
        hero_image_url = 'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=1920&q=80'
        if hero_filename:
            try:
                transform = {'width': 1600, 'quality': 75}
                hero_image_url = get_image_url(f"uploads/{hero_filename}", transform)
            except Exception as e:
                app.logger.error(f"Error generating hero image URL: {e}")
        return dict(hero_image_url=hero_image_url)

    @app.context_processor
    def inject_photos():
        from .db import get_supabase_client
        supabase = get_supabase_client()
        
        photos = []
        try:
            response = supabase.from_('photos').select('filename').eq('is_visible', True).order('created_at', desc=True).execute()
            
            if response.data:
                for photo_data in response.data:
                    filename = photo_data.get('filename')
                    if not filename: continue
                    
                    thumb_transform = {'width': 250, 'height': 250, 'resize': 'cover', 'quality': 60}
                    full_transform = {'width': 1280, 'height': 720, 'quality': 75}
                    
                    photos.append({
                        'thumbnail': get_image_url(f"photos/{filename}", thumb_transform),
                        'full': get_image_url(f"photos/{filename}", full_transform),
                        'filename': filename
                    })

        except Exception as e:
            app.logger.error(f"Error fetching photos: {e}")

        if not photos:
            fallback_urls = app.config['GALLERY_FALLBACK_URLS']
            for i, url in enumerate(fallback_urls):
                photos.append({'thumbnail': url, 'full': url, 'filename': f'fallback_{i+1}.jpg'})

        return dict(photos=photos)

    return app