import os
from flask import Flask, url_for


def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY'),
        DATABASE=os.path.join(app.instance_path, 'rsvp.db'),
        ADMIN_USERNAME=os.environ.get('WEDDING_ADMIN_USERNAME', 'admin'),
        ADMIN_PASSWORD=os.environ.get('WEDDING_ADMIN_PASSWORD', 'wedding2026'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'photos'),
        HERO_UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'}
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
        os.makedirs(app.config['UPLOAD_FOLDER'])
        os.makedirs(app.config['HERO_UPLOAD_FOLDER'])
        os.makedirs(os.path.join(app.root_path, 'static', 'css'))
    except OSError:
        pass

    # Initialize database
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
        from .db import get_setting
        hero_filename = get_setting('hero_image_filename')
        hero_image_url = url_for('static', filename='uploads/' + hero_filename) if hero_filename else 'https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=1920&q=80'
        return dict(hero_image_url=hero_image_url)

    @app.context_processor
    def inject_photos():
        from .db import get_db
        with get_db() as conn:
            photos = conn.execute('SELECT filename FROM photos ORDER BY created_at DESC').fetchall()
        return dict(photos=photos)

    return app