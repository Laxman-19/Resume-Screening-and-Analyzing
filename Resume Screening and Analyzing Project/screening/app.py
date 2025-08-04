from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
import os
import PyPDF2
import docx2txt
from pyresparser import ResumeParser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime, timedelta
import secrets
from models import db, AptitudeTest, TestLink, Candidate



screening_bp = Blueprint('screeningbp', __name__, template_folder='templates')

UPLOAD_FOLDER = 'uploads/'
predefined_content = "Hello, this is a predefined message from Flask app."
emails = []  # Global list to store extracted emails


# Resume Text Extraction Functions
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
    return text

def extract_text_from_docx(file_path):
    return docx2txt.process(file_path)

def extract_text_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def extract_text(file_path):
    if file_path.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        return extract_text_from_docx(file_path)
    elif file_path.endswith('.txt'):
        return extract_text_from_txt(file_path)
    else:
        return ""
    

# Send email function
def send_email(to_email):
    from_email = "laxman19.sawant@gmail.com"  # Your email here
    from_password = "dtdp vtdf ziqa rebn"  # Your email password here

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = 'Predefined Message'
    msg.attach(MIMEText(predefined_content, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")


@screening_bp.route('/')
def screening_home():
    available_tests = AptitudeTest.query.all()
    return render_template('screening.html', available_tests=available_tests)


@screening_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@screening_bp.route('/matcher', methods=['GET', 'POST'])
def matcher():
    global emails  
    emails = []  

    # Get available tests for the template
    available_tests = AptitudeTest.query.all()

    if request.method == 'POST':
        job_description = request.form.get('job_description')
        resume_files = request.files.getlist('resumes')

        resumes = []
        all_resumes_paths = []

        for each_resume_file in resume_files:
            filename = os.path.join(UPLOAD_FOLDER, each_resume_file.filename)
            each_resume_file.save(filename)
            resumes.append(extract_text(filename))
            all_resumes_paths.append(filename)

        if not resumes or not job_description:
            return render_template('screening.html', message="Please Enter Job Description and Upload Resumes", available_tests=available_tests)

        vectorizer = TfidfVectorizer().fit_transform([job_description] + resumes)
        vectors = vectorizer.toarray()

        job_vector = vectors[0]
        resume_vectors = vectors[1:]
        similarities = cosine_similarity([job_vector], resume_vectors)[0]

        top_indices = similarities.argsort()[-5:][::-1]
        top_resumes = [resume_files[i].filename for i in top_indices]
        similarity_scores = [round(similarities[i], 5) for i in top_indices]

        selected_resumes_path = [all_resumes_paths[i] for i in top_indices]
        print("Selected Resume Paths:", selected_resumes_path)

        data_to_display = []

        for resume in selected_resumes_path:
            data = ResumeParser(resume).get_extracted_data()
            data_to_display.append(data)
            if data and 'email' in data:
                emails.append(data['email'])  
            else:
                emails.append("Email not found")

        return render_template('screening.html', 
                            message='Top Shortlisted candidates that are match for the job description are...', 
                            resumes=top_resumes, 
                            scores=similarity_scores, 
                            people=data_to_display, 
                            zip=zip, 
                            emails=emails,
                            available_tests=available_tests)


@screening_bp.route('/send_emails', methods=['POST'])
def send_emails():
    global emails  

    if not emails:
        return redirect(url_for('screeningbp.screening_home')) 
    for email in emails:
        if email != "Email not found":  
            send_email(email)

    return redirect(url_for('screeningbp.screening_home'))

@screening_bp.route('/send_test_links', methods=['POST'])
def send_test_links():
    test_id = request.form.get('test_id')
    selected_candidates = request.form.getlist('selected_candidates[]')

    if not test_id or not selected_candidates:
        flash('Please select a test and at least one candidate', 'error')
        return redirect(url_for('screeningbp.matcher'))

    test = AptitudeTest.query.get(test_id)
    if not test:
        flash('Selected test not found', 'error')
        return redirect(url_for('screeningbp.matcher'))

    for candidate_data in selected_candidates:
        data = json.loads(candidate_data)
        
        # Create or get candidate
        candidate = Candidate.query.filter_by(email=data['email']).first()
        if not candidate:
            candidate = Candidate(
                name=data['name'],
                email=data['email']
            )
            db.session.add(candidate)
        
        # Create test link
        token = secrets.token_urlsafe(32)
        test_link = TestLink(
            token=token,
            test_id=test_id,
            candidate_id=candidate.id,
            expires_at=datetime.utcnow() + timedelta(days=7)  # Link expires in 7 days
        )
        db.session.add(test_link)
        
        # Send email with test link
        test_url = url_for('aptitude.take_test', token=token, _external=True)
        send_test_email(candidate.email, candidate.name, test.title, test_url)

    db.session.commit()
    flash('Aptitude test links have been sent to selected candidates', 'success')
    return redirect(url_for('screeningbp.matcher'))

def send_test_email(to_email, candidate_name, test_title, test_url):
    from_email = "laxman19.sawant@gmail.com"  # Your email here
    from_password = "dtdp vtdf ziqa rebn"  # Your email password here

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = f'Aptitude Test: {test_title}'

    email_body = f"""
    Dear {candidate_name},

    You have been selected to take an aptitude test as part of your application process.

    Test Details:
    - Test Name: {test_title}
    - Valid for: 7 days

    Please click the following link to start your test:
    {test_url}

    Note: This link will expire in 7 days. Please complete the test before the expiration.

    Best regards,
    The Recruitment Team
    """

    msg.attach(MIMEText(email_body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        print(f"Test link sent to {to_email}")
    except Exception as e:
        print(f"Failed to send test link to {to_email}: {e}")

@screening_bp.route('/get_available_tests')
def get_available_tests():
    tests = AptitudeTest.query.all()
    return jsonify([{
        'id': test.id,
        'title': test.title
    } for test in tests])
