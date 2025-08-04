from flask import Flask, render_template, request
from screening.app import screening_bp
from optimizing.app import optimizing_bp
from aptitude.app import aptitude_bp
from models import db

app = Flask(__name__)
app.secret_key = "laxman_key_123"


# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resume_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create database tables
with app.app_context():
    db.create_all()


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    name = None  
    message = None

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        feedback = request.form['feedback']

        message = "Thanks for reaching out."

    return render_template('contact.html', message=message, name=name)


@app.route('/features')
def features():
    return render_template('feature.html')




# Register your existing projects
app.register_blueprint(screening_bp, url_prefix="/screening")
app.register_blueprint(optimizing_bp, url_prefix="/optimizing")
app.register_blueprint(aptitude_bp, url_prefix="/aptitude")

if __name__ == '__main__':
    app.run(debug=True)
