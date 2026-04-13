import os
from flask import Flask, url_for, current_app


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
            'https://images.unsplash.com/photo-1510076857177-7470076d4098?auto=format&fit=crop&w=800&q=60',
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

    @app.context_processor
    def inject_hero_image():
        from .db import get_setting, get_supabase_client
        supabase = get_supabase_client()
        bucket_name = current_app.config['SUPABASE_BUCKET']
        hero_filename = get_setting('hero_image_filename')
        hero_image_url = 'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=1920&q=80'
        if hero_filename:
            try:
                hero_image_url = supabase.storage.from_(bucket_name).get_public_url(f"uploads/{hero_filename}")
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
            response = supabase.from_('photos').select('filename').order('created_at', desc=True).execute()
            if response.data:
                for photo_data in response.data:
                    filename = photo_data['filename']
                    public_url = supabase.storage.from_(bucket_name).get_public_url(f"photos/{filename}")
                    photos.append({'filename': filename, 'url': public_url})
        except Exception as e:
            app.logger.error(f"Error fetching photos from Supabase: {e}")
        
        if not photos:
            fallback_urls = app.config['GALLERY_FALLBACK_URLS']
            for i, url in enumerate(fallback_urls):
                photos.append({'filename': f'fallback_{i+1}.jpg', 'url': url})

        return dict(photos=photos)

    return app