from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory
import PyPDF2
import docx2txt
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import re



optimizing_bp = Blueprint('optimizingbp', __name__, template_folder='templates')


UPLOAD_FOLDER = 'uploads/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 


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

def extract_text(file_path):
    if file_path.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith('.docx'):
        return extract_text_from_docx(file_path)
    else:
        return ""



def get_gemini_response(input):
    model=genai.GenerativeModel('gemini-1.5-pro')
    response=model.generate_content(input)
    return response.text

input_prompt = """
Hey, act like a skilled and highly experienced ATS (Applicant Tracking System)
with a deep understanding of software engineering, data science, data analytics, and big data engineering.
Your task is to evaluate the resume based on the given job description. The job market is competitive,
so provide the best possible feedback for improving the resume. Assign a percentage match based 
on the job description and list missing keywords with high accuracy.

resume: {text}
description: {jd}

I want the response in one single JSON string with the structure:
{{
    "JD Match": "%", 
    "MissingKeywords": [], 
    "Profile Summary": ""
}}
"""


def get_course_suggestions(skills):
    print("Skills received for courses:", skills)  # Debug print
    if not skills:
        return {}

    course_suggestions = {}

    for skill in skills:
        course_suggestions[skill] = {
            "title": f"Explore {skill} Courses on Coursera",
            "url": f"https://www.coursera.org/courses?query={skill}"
        }
    print("Generated course suggestions:", course_suggestions)  # Debug print
    return course_suggestions


@optimizing_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@optimizing_bp.route('/')
def optimizing_home():
    return render_template('optimizing.html')


@optimizing_bp.route('/analyzer', methods=['GET', 'POST'])
def analyzer():

    if request.method == 'POST':
        job_description = request.form.get('job_description')
        resume_file_list = request.files.getlist('resume')  # This is a list

        resume_file = resume_file_list[0]
    
        filename = os.path.join(UPLOAD_FOLDER, resume_file.filename)
        resume_file.save(filename)
        resume_text = extract_text(filename)



        load_dotenv()
        
        # Configure Generative AI
        api_key = os.getenv("GOOGLE_API_KEY")
        # if not api_key:
        #     return render_template('optimizing.html', message="API Key not found. Check your .env file.")
        genai.configure(api_key=api_key)

        models = genai.list_models()
        print(models)

                
        # Get and parse response
        formatted_prompt = input_prompt.format(text=resume_text, jd=job_description)
        response = get_gemini_response(formatted_prompt)

        if not response or response.strip() == "":
            return render_template('optimizing.html', message="Received empty response from Gemini AI. Please try again.")
        
        print("Raw Response from Gemini AI:========================", response)
        print('========================================================================')


        match = re.search(r'\{.*\}', response, re.DOTALL)  # Find the JSON structure
        if match:
            response_cleaned = match.group(0)  # Extract the matched JSON
        else:
            return render_template('optimizing.html', message="Invalid response format from Gemini AI. Please try again.")

        try:
            response_json = json.loads(response_cleaned)  
        except json.JSONDecodeError as e:
            print("Error decoding JSON:", e)
            return render_template('optimizing.html', message="Invalid response format from Gemini AI")
        

        



        match_percentage = response_json.get("JD Match", "N/A")
        missing_keywords = response_json.get("MissingKeywords", [])
        profile_summary = response_json.get("Profile Summary", "No summary available")


        print('saaa', match_percentage)
        print('saaa', missing_keywords)
        print('saaa', profile_summary)


        course_suggestions = get_course_suggestions(missing_keywords)
    

        return render_template('optimizing.html', message='We analysed the resume and found out that...', 
                               match_percentage=match_percentage, missing_keywords=missing_keywords, 
                               profile_summary=profile_summary, course_suggestions=course_suggestions)
    
    return render_template('optimizing.html')  # Handle GET request properly