from flask import Flask

def index():
    return "welcome to the index page"


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'Chick3nCoopDissonanc3!'

    from flask_gui.locations_blueprint import locations_bp
    from flask_gui.home_blueprint import home_bp

    app.register_blueprint(home_bp, url_prefix='/')
    app.register_blueprint(locations_bp, url_prefix='/')

    return app

def run(port: int = 5000):
    app = create_app()
    app.run(debug=True, port=port)

if __name__ == "__main__":
    run(port=5001)