from flask import Flask, render_template, request, redirect, session, url_for
from flask import Response as R
from flask_sqlalchemy import SQLAlchemy
from flask import jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
import uuid


app = Flask(__name__,  static_url_path='/static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///surveys.db'
app.config['SECRET_KEY'] = 'your_secret_key'  # Set a secure secret key
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
bcrypt = Bcrypt(app)

def check_password(hash, password) -> bool:
    return bcrypt.check_password_hash(hash, password)

def encrypy_password(password):
    return bcrypt.generate_password_hash(password)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    surveys_approved = db.relationship('Survey', backref='approver', lazy=True)

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    approved = db.Column(db.Boolean, default=False)
    classes = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)
    classDescriptions = db.Column(db.Text, nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    questions = db.relationship('Question', backref='survey', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    responses = db.relationship('Response', backref='question', lazy=True)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tuple_id = db.Column(db.Integer, unique=False) # The person's id
    classid = db.Column(db.Integer, nullable=False) # This person's self-identified class
    survey_id = db.Column(db.Integer, nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'),nullable=False)
    choice = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def loader_user(id):
    return User.query.get(id)
 
@app.route('/')
def index():
    surveys = Survey.query.filter_by(approved=True).all()
    isauth = False
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            isauth = True
    return render_template('index.html', header="Available Surveys",surveys=surveys, isauth=isauth)

@app.route('/admin')
@login_required
def admin():
    surveys = Survey.query.filter_by(approved=False).all()
    isauth = True
    return render_template('approve.html', header="Surveys to Approve",surveys=surveys, isauth=isauth)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username'].lower()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password(user.password, password):
            login_user(user)
            session['user_id'] = user.id  # Manually set the session user_id
            return redirect(url_for("index"))
        else:
            return render_template("login.html", message="Invalid Credentials")

    return render_template("login.html", message="Enter Credentials")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("index"))

@app.route('/create_survey', methods=['POST'])
def create_survey():
    name = request.form['name']
    questions = request.form['questions'].split('\n')
    description = request.form['description']
    classes = request.form['classes'].split('\n')
    classDescriptions = request.form['classDescription']
    survey = Survey(name=name, description=description.strip(), classes=','.join(classes), classDescriptions=classDescriptions)
    survey.approved = False
    db.session.add(survey)
    db.session.commit()

    for question_text in questions:
        question = Question(text=question_text, survey_id=survey.id)
        db.session.add(question)

    db.session.commit()
    return redirect('/')

@app.route('/survey/<int:survey_id>')
def take_survey(survey_id):
    survey = Survey.query.get(survey_id)
    return render_template('survey.html', survey=survey)

@app.route('/submit_response/<int:survey_id>', methods=['POST'])
def submit_response(survey_id):
    survey = Survey.query.get(survey_id)
    response_data = request.form.to_dict()

    # Assuming classid is in the form data
    classid = int(response_data.get('classid', 0))  # Default to 0 if not provided
    id = uuid.uuid4().int >> (128 - 32)
    for question_id, choice in response_data.items():
        if question_id != 'classid':
            # Generate a random tuple_id using uuid
            response = Response(tuple_id=id,survey_id=survey.id, question_id=question_id, choice=int(choice), classid=classid)
            db.session.add(response)

    db.session.commit()
    return jsonify({'message': 'Response submitted successfully'}), 200


@app.route('/approve_survey/<int:survey_id>')
@login_required
def approve_survey(survey_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if user:
        survey = Survey.query.get(survey_id)
        if survey and not survey.approved:
            survey.approved = True
            survey.approver = user
            db.session.commit()

    return redirect('/admin')


@app.route('/like/<int:survey_id>')
def like(survey_id):
    s = Survey.query.filter_by(id=survey_id).first()
    s.likes += 1
    db.session.add(s)
    db.session.commit()
    return redirect('/survey/' + str(survey_id))

@app.route('/dislike/<int:survey_id>')
def dislike(survey_id):
    s = Survey.query.filter_by(id=survey_id).first()
    s.likes -= 1
    db.session.add(s)
    db.session.commit()
    return redirect('/survey/' + str(survey_id))

@app.route('/download_survey/<int:survey_id>')
def download_survey(survey_id):
    survey = Survey.query.get(survey_id)

    if not survey:
        return redirect(url_for('index'))

    # Prepare CSV content
    csv_content = generate_csv_content(survey)

    # Set up response headers
    headers = {
        "Content-Disposition": f"attachment; filename={survey.name.replace(' ', '-')}.csv",
        "Content-Type": "text/csv",
    }

    return R(csv_content, headers=headers)

@app.route('/get_data/<int:survey_id>')
def get_data(survey_id):
    survey = Survey.query.get(survey_id)

    if not survey:
        return redirect(url_for('index'))

    # Prepare CSV content
    csv_content = generate_csv_content(survey)
    lines = csv_content.splitlines()
    idx = 0
    qn_idices = []
    cl_indices = []
    for it in lines[0].split(','):
        if it.startswith('question'):
            qn_idices.append(idx)
        elif it.startswith('class'):
            cl_indices.append(idx)
        idx += 1
    idx = 0
    json_content = {}
    json_content['responses'] = []
    for line in lines:
        features = []
        classes = []
        if(idx == 0):
            pass
        else:
            col = 0
            for it in line.split(','):
                if col in qn_idices:
                    features.append(it)
                elif col in cl_indices:
                    classes.append(it)
                col += 1
        if len(features) > 0 and len(classes) > 0:
            json_content['responses'].append(
                {'features': features,
                'classes': classes}
            )
        idx += 1
    json_content['questions'] = []
    json_content['classes'] = []
    idx = 0
    for it in lines[0].split(','):
        if idx in qn_idices:
            json_content['questions'].append(it)
        elif idx in cl_indices:
            json_content['classes'].append(it)
        idx += 1
    return jsonify(json_content)

def generate_csv_content(survey):
    # Prepare headers for questions and classes
    questions_headers = [f"question_{question.text.strip()}" for question in survey.questions]
    classes_headers = [f"class_{class_id.strip()}" for class_id in survey.classes.split(',')]

    # Combine all headers
    csv_headers = ["tuple_id"] + questions_headers + classes_headers

    # Initialize the CSV content with headers
    csv_content = [",".join(csv_headers)]

    # Query unique tuple_ids
    unique_tuple_ids = db.session.query(Response.tuple_id).filter_by(survey_id=survey.id).distinct().all()
    unique_tuple_ids = [a[0] for a in unique_tuple_ids]

    # Iterate over unique tuple_ids
    for tid in unique_tuple_ids:
        # Initialize a line for the current tuple_id
        line = [str(tid)]

        # Iterate over questions
        for q in survey.questions:
            # Find the response for the current question
            response = Response.query.filter_by(survey_id=survey.id, tuple_id=tid, question_id=q.id).first()

            # Append 1 if the response exists, else 0
            line.append(str(int(response.choice) if response else -1))

        # Iterate over classes
        for class_id in range(len(survey.classes.split(','))):
            # Check if any response exists for the current class
            response_exists = Response.query.filter_by(survey_id=survey.id, tuple_id=tid, classid=class_id).first()

            # Append 1 if response exists, else 0
            line.append(str(1 if response_exists else 0))

        # Join the line and add it to the CSV content
        csv_content.append(",".join(line))

    # Join all lines to form the complete CSV content
    return "\n".join(csv_content)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        admin_user = User.query.filter_by(username="admin").first()
        if not admin_user:
            admin_user = User(username = "admin", password=encrypy_password("admin123"))
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True)