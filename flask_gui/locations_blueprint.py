from flask import Blueprint, render_template
import requests
import pandas as pd

locations_bp = Blueprint('locations', __name__)

@locations_bp.route('/locations_home')
def home():
    return render_template("locations/locations_home.html")

@locations_bp.route('/locations')
def view_locations():
    locations = requests.get('http://127.0.0.1:5000/locations').json()

    my_html = pd.DataFrame([x for x in locations['data']]).to_html(classes='mystyle',
                                                     show_dimensions=True,
                                                     na_rep='-',
                                                     float_format=lambda x: "${:.2f}".format(x))

    return render_template("locations/locations.html", locations_html=my_html)

