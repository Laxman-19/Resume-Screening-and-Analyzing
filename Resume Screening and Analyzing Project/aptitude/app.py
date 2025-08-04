from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from models import db, Candidate, AptitudeTest, Question, Option, TestLink, TestAttempt, Answer
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import secrets

aptitude_bp = Blueprint('aptitude', __name__, template_folder='templates')

# Email configuration
EMAIL_SENDER = "laxman19.sawant@gmail.com"  # Update with your email
EMAIL_PASSWORD = "dtdp vtdf ziqa rebn"  # Update with your app password

# Helper function to send test link via email
def send_test_link_email(to_email, candidate_name, test_title, test_link):
    """Send an email with the aptitude test link to a candidate"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = to_email
    msg['Subject'] = f"Invitation to take {test_title} Aptitude Test"
    
    email_body = f"""
    <html>
    <body>
        <h2>Hello {candidate_name},</h2>
        <p>You have been selected to take an aptitude test as part of your application process.</p>
        <p><strong>Test:</strong> {test_title}</p>
        <p>Please click the link below to start your test:</p>
        <p><a href="{test_link}" style="padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Start Test</a></p>
        <p>This link will expire in 7 days.</p>
        <p>Good luck!</p>
        <p>Best regards,<br>HR Team</p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(email_body, 'html'))
    
    try:
        # Try SSL first
        try:
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        except:
            # If SSL fails, try TLS
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, to_email, text)
        server.quit()
        print(f"Successfully sent email to {to_email}")
        return True
    except Exception as e:
        error_msg = f"Failed to send email to {to_email}: {str(e)}"
        print(error_msg)
        flash(error_msg, 'error')
        return False

# Routes for HR to manage tests
@aptitude_bp.route('/')
def aptitude_home():
    """Home page for aptitude test management"""
    tests = AptitudeTest.query.order_by(AptitudeTest.created_at.desc()).all()
    return render_template('aptitude/home.html', tests=tests)

@aptitude_bp.route('/delete_test/<int:test_id>', methods=['POST'])
def delete_test(test_id):
    """Delete an aptitude test and all associated data"""
    test = AptitudeTest.query.get_or_404(test_id)
    
    # Delete all associated test attempts and answers
    for attempt in test.test_attempts:
        # Delete answers associated with this attempt
        Answer.query.filter_by(attempt_id=attempt.id).delete()
    TestAttempt.query.filter_by(test_id=test_id).delete()
    
    # Delete all test links
    TestLink.query.filter_by(test_id=test_id).delete()
    
    # Delete all questions and their options
    for question in test.questions:
        # Delete options associated with this question
        Option.query.filter_by(question_id=question.id).delete()
    Question.query.filter_by(test_id=test_id).delete()
    
    # Finally, delete the test
    db.session.delete(test)
    db.session.commit()
    
    flash('Test has been deleted successfully.', 'success')
    return redirect(url_for('aptitude.aptitude_home'))

@aptitude_bp.route('/create_test', methods=['GET', 'POST'])
def create_test():
    """Create a new aptitude test"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        time_limit = request.form.get('time_limit', 60, type=int)
        passing_score = request.form.get('passing_score', 60, type=int)
        created_by = request.form.get('created_by')
        
        # Create new test
        new_test = AptitudeTest(
            title=title,
            description=description,
            time_limit=time_limit,
            passing_score=passing_score,
            created_by=created_by
        )
        
        db.session.add(new_test)
        db.session.commit()
        
        return redirect(url_for('aptitude.edit_test', test_id=new_test.id))
    
    return render_template('aptitude/create_test.html')

@aptitude_bp.route('/edit_test/<int:test_id>', methods=['GET', 'POST'])
def edit_test(test_id):
    """Edit an existing aptitude test"""
    test = AptitudeTest.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    
    return render_template('aptitude/edit_test.html', test=test, questions=questions)

@aptitude_bp.route('/add_question/<int:test_id>', methods=['POST'])
def add_question(test_id):
    """Add a question to a test"""
    test = AptitudeTest.query.get_or_404(test_id)
    
    question_text = request.form.get('question_text')
    question_type = request.form.get('question_type', 'multiple_choice')
    
    # Create new question
    new_question = Question(
        test_id=test_id,
        text=question_text,
        question_type=question_type
    )
    
    db.session.add(new_question)
    db.session.commit()
    
    # Add options
    options = request.form.getlist('option_text[]')
    correct_option = request.form.get('correct_option', type=int)
    
    for i, option_text in enumerate(options):
        if option_text.strip():  # Only add non-empty options
            new_option = Option(
                question_id=new_question.id,
                option_text=option_text,
                is_correct=(i == correct_option)
            )
            db.session.add(new_option)
    
    db.session.commit()
    
    return redirect(url_for('aptitude.edit_test', test_id=test_id))

@aptitude_bp.route('/send_test/<int:test_id>', methods=['GET', 'POST'])
def send_test(test_id):
    """Send test links to candidates"""
    test = AptitudeTest.query.get_or_404(test_id)
    
    if request.method == 'POST':
        # Get candidate emails from the form
        candidate_emails = request.form.get('candidate_emails', '').split(',')
        base_url = request.host_url.rstrip('/')
        
        for email in candidate_emails:
            email = email.strip()
            if not email:
                continue
                
            # Check if candidate exists
            candidate = Candidate.query.filter_by(email=email).first()
            if not candidate:
                # Create new candidate
                candidate = Candidate(
                    name=email.split('@')[0],  # Use part of email as name
                    email=email
                )
                db.session.add(candidate)
                db.session.commit()
            
            # Create test link with token
            expires_at = datetime.utcnow() + timedelta(days=7)
            token = secrets.token_urlsafe(32)  # Generate a secure random token
            
            test_link = TestLink(
                token=token,
                candidate_id=candidate.id,
                test_id=test_id,
                expires_at=expires_at
            )
            
            db.session.add(test_link)
            db.session.commit()
            
            # Generate test URL
            test_url = f"{base_url}/aptitude/take_test/{test_link.token}"
            
            # Send email with test link
            send_test_link_email(
                email, 
                candidate.name, 
                test.title, 
                test_url
            )
        
        flash('Test links have been sent to the candidates.')
        return redirect(url_for('aptitude.aptitude_home'))
    
    return render_template('aptitude/send_test.html', test=test)

# Routes for candidates to take tests
@aptitude_bp.route('/take_test/<token>')
def take_test(token):
    """Page for candidates to take a test"""
    # Find the test link
    test_link = TestLink.query.filter_by(token=token).first_or_404()
    
    # Check if link is expired
    if test_link.expires_at < datetime.utcnow():
        return render_template('aptitude/expired.html')
    
    # Check if link is already used
    if test_link.is_used:
        return render_template('aptitude/already_taken.html')
    
    # Get test and candidate
    test = test_link.test
    candidate = test_link.candidate
    
    # Create a new test attempt
    test_attempt = TestAttempt(
        candidate_id=candidate.id,
        test_id=test.id,
        start_time=datetime.utcnow()
    )
    
    db.session.add(test_attempt)
    db.session.commit()
    
    # Get questions for the test
    questions = Question.query.filter_by(test_id=test.id).all()
    
    # Prepare questions and options for the template
    questions_data = []
    for question in questions:
        options = Option.query.filter_by(question_id=question.id).all()
        questions_data.append({
            'id': question.id,
            'text': question.text,
            'type': question.question_type,
            'options': options
        })
    
    return render_template(
        'aptitude/take_test.html',
        test=test,
        candidate=candidate,
        questions=questions_data,
        attempt_id=test_attempt.id,
        time_limit=test.time_limit
    )

@aptitude_bp.route('/submit_test/<int:attempt_id>', methods=['POST'])
def submit_test(attempt_id):
    """Handle test submission"""
    # Get the test attempt
    attempt = TestAttempt.query.get_or_404(attempt_id)
    
    # Mark the test as completed
    attempt.end_time = datetime.utcnow()
    
    # Get the test
    test = attempt.test
    
    # Process answers
    data = request.get_json()
    answers = data.get('answers', {})
    
    correct_count = 0
    total_questions = len(answers)
    
    # Record answers and calculate score
    for question_index, option_id in answers.items():
        question = Question.query.get(int(question_index))
        selected_option = Option.query.get(int(option_id))
        
        # Create answer record
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question.id,
            selected_option_id=option_id,
            is_correct=selected_option.is_correct
        )
        
        if selected_option.is_correct:
            correct_count += 1
            
        db.session.add(answer)
    
    # Calculate score as percentage
    if total_questions > 0:
        score = (correct_count / total_questions) * 100
    else:
        score = 0
    
    attempt.score = score
    
    # Mark test link as used - Fixed the query to find the correct test link
    test_link = TestLink.query.filter_by(
        candidate_id=attempt.candidate_id,
        test_id=attempt.test_id,
        is_used=False  # Only get unused links
    ).order_by(TestLink.created_at.desc()).first()  # Get the most recent link
    
    if test_link:
        test_link.is_used = True
        db.session.add(test_link)
    
    # Determine if passed based on test's passing score
    attempt.passed = float(score) >= float(test.passing_score)
    print(f"Score: {score}, Passing Score: {test.passing_score}, Passed: {attempt.passed}")  # Debug print
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'redirect': url_for('aptitude.test_resultcopy', attempt_id=attempt_id)
    })

@aptitude_bp.route('/test_results/<int:attempt_id>')
def test_results(attempt_id):
    """Show test results to the candidate"""
    attempt = TestAttempt.query.get_or_404(attempt_id)
    test = attempt.test
    candidate = attempt.candidate
    
    # Get answers with proper question filtering
    answers = (Answer.query
              .join(Question, Answer.question_id == Question.id)
              .filter(Answer.attempt_id == attempt_id)
              .filter(Question.test_id == test.id)
              .order_by(Question.id)
              .all())
    
    return render_template(
        'aptitude/test_results.html',
        attempt=attempt,
        test=test,
        candidate=candidate,
        answers=answers
    )

# HR dashboard to view results
@aptitude_bp.route('/results/<int:test_id>')
def view_results(test_id):
    """View results for a specific test"""
    test = AptitudeTest.query.get_or_404(test_id)
    attempts = TestAttempt.query.filter_by(test_id=test_id).order_by(TestAttempt.end_time.desc()).all()
    
    return render_template(
        'aptitude/view_results.html',
        test=test,
        attempts=attempts
    ) 