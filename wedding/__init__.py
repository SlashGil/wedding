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
        # The local SQLite database is no longer used
        # DATABASE=os.path.join(app.instance_path, 'rsvp.db'), 
        ADMIN_USERNAME=os.environ.get('WEDDING_ADMIN_USERNAME', 'admin'),
        ADMIN_PASSWORD=os.environ.get('WEDDING_ADMIN_PASSWORD', 'wedding2026'),
        # Local upload folders are no longer used as storage is handled by Supabase
        # UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'photos'), 
        # HERO_UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'), 
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
        SUPABASE_URL=os.environ.get('SUPABASE_URL'),
        SUPABASE_KEY=os.environ.get('SUPABASE_KEY'),
        SUPABASE_BUCKET='wedding-images', # Assuming a bucket named 'wedding-images'
        GALLERY_FALLBACK_IMAGES=[ # Add your fallback image filenames here
            'gallery_fallback_1.jpg',
            'gallery_fallback_2.jpg',
            'gallery_fallback_3.jpg',
            'gallery_fallback_4.jpg',
            'gallery_fallback_5.jpg',
            'gallery_fallback_6.jpg',
        ]
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        # These local upload folders are no longer needed with Supabase storage
        # os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # os.makedirs(app.config['HERO_UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'css'), exist_ok=True)
        # Ensure the fallback image directory exists
        os.makedirs(os.path.join(app.root_path, 'static', 'img', 'gallery_fallbacks'), exist_ok=True)
    except OSError:
        pass

    # Initialize database (now Supabase client)
    from . import db
    db.init_app(app)

    # Register blueprints
    from . import auth, main_routes, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(admin.bp)

    # Make '/' the default endpoint for the main blueprint
    app.add_url_rule('/', endpoint='index')

    # Context processors to inject variables into all templates
    @app.context_processor
    def inject_hero_image():
        from .db import get_setting, get_supabase_client
        supabase = get_supabase_client()
        bucket_name = current_app.config['SUPABASE_BUCKET']
        hero_filename = get_setting('hero_image_filename')
        hero_image_url = 'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=1920&q=80' # Default image
        if hero_filename:
            try:
                # Get public URL from Supabase storage
                # The path for hero images is 'uploads/'
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
                    # Get public URL from Supabase storage
                    # The path for gallery photos is 'photos/'
                    public_url = supabase.storage.from_(bucket_name).get_public_url(f"photos/{filename}")
                    photos.append({'filename': filename, 'url': public_url})
        except Exception as e:
            app.logger.error(f"Error fetching photos from Supabase: {e}")
        
        # If no photos are found in Supabase, use static fallback images
        if not photos:
            for filename in app.config['GALLERY_FALLBACK_IMAGES']:
                photos.append({'filename': filename, 'url': url_for('static', filename=f'img/gallery_fallbacks/{filename}')})

        return dict(photos=photos)

    return app