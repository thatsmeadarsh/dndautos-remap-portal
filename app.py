import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import requests
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
import tempfile
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-replace-in-production')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Azure Blob Storage setup
AZURE_STORAGE_ENABLED = False
if os.environ.get('ENABLE_AZURE_STORAGE') == 'true':
    try:
        # Use DefaultAzureCredential for managed identity in Azure
        if os.environ.get('AZURE_STORAGE_CONNECTION_STRING'):
            blob_service_client = BlobServiceClient.from_connection_string(
                os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
            )
        else:
            account_url = f"https://{os.environ.get('AZURE_STORAGE_ACCOUNT')}.blob.core.windows.net"
            credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        
        container_name = os.environ.get('AZURE_STORAGE_CONTAINER', 'ecufiles')
        # Create container if it doesn't exist
        try:
            container_client = blob_service_client.get_container_client(container_name)
            container_client.get_container_properties()
        except Exception:
            container_client = blob_service_client.create_container(container_name)
        
        AZURE_STORAGE_ENABLED = True
    except Exception as e:
        print(f"Azure Blob Storage not configured: {e}")
        AZURE_STORAGE_ENABLED = False
else:
    print("Azure Blob Storage disabled for development mode")

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class
class User(UserMixin):
    def __init__(self, id, email, password_hash, is_admin=False, is_superadmin=False):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.is_superadmin = is_superadmin

# User class with superadmin flag
class User(UserMixin):
    def __init__(self, id, email, password_hash, is_admin=False, is_superadmin=False):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.is_superadmin = is_superadmin

# In-memory user store (replace with database in production)
users = {
    '1': User('1', 'aswin-tvm@dndautos.co.uk', 
              generate_password_hash('DnD@Remap2024!'), False, False),
    '2': User('2', 'sharath-admin@dndautos.co.uk', 
              generate_password_hash('Admin@DnD2024!'), True, False),
    '3': User('3', 'superadmin@dndautos.co.uk',
              generate_password_hash('Super@DnD2024!'), True, True)
}

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Data storage (replace with database in production)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

def get_submissions():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_submission(submission):
    submissions = get_submissions()
    submissions.append(submission)
    with open(DATA_FILE, 'w') as f:
        json.dump(submissions, f)

def update_submission(submission_id, tuned_file):
    submissions = get_submissions()
    for submission in submissions:
        if submission['id'] == submission_id:
            submission['tuned_file'] = tuned_file
            submission['tuned_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(DATA_FILE, 'w') as f:
        json.dump(submissions, f)

def delete_submission(submission_id):
    submissions = get_submissions()
    submissions = [s for s in submissions if s['id'] != submission_id]
    with open(DATA_FILE, 'w') as f:
        json.dump(submissions, f)

# File handling functions
def save_file_to_azure(file, filename, submission_id):
    if not AZURE_STORAGE_ENABLED:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return filename
    
    blob_name = f"{submission_id}/{filename}"
    blob_client = blob_service_client.get_blob_client(
        container=container_name, 
        blob=blob_name
    )
    
    blob_client.upload_blob(file, overwrite=True)
    return blob_name

def get_file_from_azure(blob_name):
    if not AZURE_STORAGE_ENABLED:
        return os.path.join(app.config['UPLOAD_FOLDER'], blob_name)
    
    blob_client = blob_service_client.get_blob_client(
        container=container_name, 
        blob=blob_name
    )
    
    # Download to a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    download_stream = blob_client.download_blob()
    temp_file.write(download_stream.readall())
    temp_file.close()
    
    return temp_file.name

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_found = None
        for user_id, user in users.items():
            if user.email == email:
                user_found = user
                break
        
        if user_found and check_password_hash(user_found.password_hash, password):
            login_user(user_found)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    submissions = get_submissions()
    
    # Apply filters if provided
    reg_filter = request.args.get('reg', '').strip().upper()
    make_filter = request.args.get('make', '').strip().upper()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    status_filter = request.args.get('status', '')
    
    if reg_filter or make_filter or date_from or date_to or status_filter:
        filtered_submissions = []
        for submission in submissions:
            # Registration filter
            if reg_filter and reg_filter not in submission.get('registration_number', '').upper():
                continue
                
            # Make filter
            if make_filter and make_filter not in submission.get('vehicle_make', '').upper():
                continue
                
            # Date filters
            submission_date = submission.get('submitted_date', '').split(' ')[0] if submission.get('submitted_date') else ''
            if date_from and submission_date and submission_date < date_from:
                continue
            if date_to and submission_date and submission_date > date_to:
                continue
                
            # Status filter
            if status_filter == 'pending' and submission.get('tuned_file'):
                continue
            if status_filter == 'completed' and not submission.get('tuned_file'):
                continue
                
            filtered_submissions.append(submission)
        
        submissions = filtered_submissions
    
    # Group submissions by registration number
    submissions_by_reg = {}
    for submission in submissions:
        reg_number = submission.get('registration_number', '')
        if not reg_number:
            # If no registration number, use ID as key
            submissions_by_reg[submission['id']] = submission
            continue
            
        # Count resubmissions for this registration
        if reg_number in submissions_by_reg:
            # If we already have a submission for this registration,
            # keep the most recent one and update resubmission count
            existing = submissions_by_reg[reg_number]
            existing_date = existing.get('submitted_date', '')
            current_date = submission.get('submitted_date', '')
            
            if current_date > existing_date:
                # Update resubmission count
                resubmission_count = existing.get('resubmission_count', 0)
                if submission.get('resubmission', False):
                    resubmission_count += 1
                submission['resubmission_count'] = resubmission_count
                submissions_by_reg[reg_number] = submission
            else:
                # Increment resubmission count on existing record
                if submission.get('resubmission', False):
                    existing['resubmission_count'] = existing.get('resubmission_count', 0) + 1
        else:
            # First submission for this registration
            submission['resubmission_count'] = 0
            submissions_by_reg[reg_number] = submission
    
    return render_template('dashboard.html', 
                          submissions=submissions, 
                          submissions_by_reg=submissions_by_reg,
                          is_admin=current_user.is_admin)

@app.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == 'POST':
        # Process form data
        registration_number = request.form.get('registration_number')
        vehicle_make = request.form.get('vehicle_make')
        vehicle_model = request.form.get('vehicle_model')
        vehicle_year = request.form.get('vehicle_year')
        file_type = request.form.get('file_type', 'ecu')
        transmission_type = request.form.get('transmission_type')
        tool_type = request.form.get('tool_type', 'slave')
        ecu_type = request.form.get('ecu_type')
        tuning_option = request.form.get('tuning_option', 'stage1')
        free_options = request.form.getlist('free_options[]')
        paid_options = request.form.getlist('paid_options[]')
        comments = request.form.get('comments', '')
        
        # Check if files were uploaded
        if 'original_file' not in request.files or 'vehicle_image' not in request.files:
            flash('Both ECU file and vehicle image are required')
            return redirect(request.url)
        
        original_file = request.files['original_file']
        vehicle_image = request.files['vehicle_image']
        
        if original_file.filename == '' or vehicle_image.filename == '':
            flash('Both ECU file and vehicle image are required')
            return redirect(request.url)
        
        # Generate submission ID
        submission_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Save files
        original_filename = secure_filename(original_file.filename)
        image_filename = secure_filename(vehicle_image.filename)
        
        original_blob = save_file_to_azure(original_file, original_filename, submission_id)
        image_blob = save_file_to_azure(vehicle_image, image_filename, submission_id)
        
        # Create submission
        submission = {
            'id': submission_id,
            'registration_number': registration_number,
            'vehicle_make': vehicle_make,
            'vehicle_model': vehicle_model,
            'vehicle_year': vehicle_year,
            'file_type': file_type,
            'transmission_type': transmission_type,
            'tool_type': tool_type,
            'ecu_type': ecu_type,
            'tuning_option': tuning_option,
            'free_options': free_options,
            'paid_options': paid_options,
            'comments': comments,
            'original_file': original_blob,
            'original_filename': original_filename,
            'vehicle_image': image_blob,
            'image_filename': image_filename,
            'submitted_by': current_user.email,
            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tuned_file': None,
            'tuned_date': None,
            'resubmission': False,
            'resubmission_notes': None,
            'original_submission_id': None,
            'resubmission_count': 0
        }
        
        save_submission(submission)
        flash('Submission successful')
        return redirect(url_for('dashboard'))
    
    return render_template('submit.html')

@app.route('/resubmit/<submission_id>', methods=['GET', 'POST'])
@login_required
def resubmit(submission_id):
    if current_user.is_admin:
        flash('Only dealers can resubmit ECU files')
        return redirect(url_for('dashboard'))
    
    submissions = get_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    
    if not submission:
        flash('Submission not found')
        return redirect(url_for('dashboard'))
    
    if submission['submitted_by'] != current_user.email:
        flash('You can only resubmit your own submissions')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'original_file' not in request.files:
            flash('ECU file is required')
            return redirect(request.url)
        
        original_file = request.files['original_file']
        notes = request.form.get('notes', '')
        
        if original_file.filename == '':
            flash('ECU file is required')
            return redirect(request.url)
        
        # Generate new submission ID
        new_submission_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Save new file
        original_filename = secure_filename(original_file.filename)
        original_blob = save_file_to_azure(original_file, original_filename, new_submission_id)
        
        # Handle optional new vehicle image
        vehicle_image = request.files.get('vehicle_image')
        if vehicle_image and vehicle_image.filename != '':
            image_filename = secure_filename(vehicle_image.filename)
            image_blob = save_file_to_azure(vehicle_image, image_filename, new_submission_id)
        else:
            # Use the original image
            image_blob = submission['vehicle_image']
            image_filename = submission['image_filename']
        
        # Count existing resubmissions for this registration
        resubmission_count = 0
        for s in submissions:
            if (s['registration_number'] == submission['registration_number'] and 
                s.get('resubmission', False)):
                resubmission_count += 1
        
        # Create new submission based on the original
        new_submission = {
            'id': new_submission_id,
            'registration_number': submission['registration_number'],
            'vehicle_make': submission['vehicle_make'],
            'vehicle_model': submission['vehicle_model'],
            'vehicle_year': submission['vehicle_year'],
            'file_type': submission.get('file_type', 'ecu'),
            'transmission_type': submission.get('transmission_type'),
            'tool_type': submission.get('tool_type', 'slave'),
            'ecu_type': submission['ecu_type'],
            'tuning_option': submission.get('tuning_option'),
            'free_options': submission.get('free_options', []),
            'paid_options': submission.get('paid_options', []),
            'comments': notes,
            'original_file': original_blob,
            'original_filename': original_filename,
            'vehicle_image': image_blob,
            'image_filename': image_filename,
            'submitted_by': current_user.email,
            'submitted_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tuned_file': None,
            'tuned_date': None,
            'resubmission': True,
            'resubmission_notes': notes,
            'original_submission_id': submission_id,
            'original_submission_date': submission.get('submitted_date'),
            'resubmission_count': resubmission_count
        }
        
        save_submission(new_submission)
        flash('ECU file resubmitted successfully')
        return redirect(url_for('dashboard'))
    
    return render_template('resubmit.html', submission=submission)

@app.route('/api/vehicle-makes')
@login_required
def vehicle_makes():
    indian_makes = [
        'MARUTI SUZUKI', 'TATA', 'MAHINDRA', 'HYUNDAI', 'HONDA', 
        'TOYOTA', 'KIA', 'FORD', 'RENAULT', 'VOLKSWAGEN', 'SKODA',
        'MG', 'JEEP', 'NISSAN', 'DATSUN', 'FIAT', 'MERCEDES-BENZ',
        'BMW', 'AUDI', 'LEXUS', 'VOLVO', 'JAGUAR', 'LAND ROVER'
    ]
    return jsonify({'makes': indian_makes})

@app.route('/api/vehicle-models')
@login_required
def vehicle_models():
    make = request.args.get('make', '').strip().upper()
    if not make:
        return jsonify({'error': 'Make parameter is required'})
    
    indian_models = {
        'MARUTI SUZUKI': ['Swift', 'Baleno', 'Dzire', 'Ertiga', 'Brezza', 'Alto', 'Wagon R'],
        'TATA': ['Nexon', 'Harrier', 'Safari', 'Tiago', 'Altroz', 'Punch', 'Tigor'],
        'MAHINDRA': ['Scorpio', 'XUV700', 'XUV300', 'Thar', 'Bolero', 'Marazzo'],
        'HYUNDAI': ['Creta', 'i20', 'Venue', 'i10', 'Verna', 'Tucson', 'Alcazar'],
        'HONDA': ['City', 'Amaze', 'WR-V', 'Jazz', 'Civic'],
        'TOYOTA': ['Innova', 'Fortuner', 'Glanza', 'Urban Cruiser', 'Camry'],
        'KIA': ['Seltos', 'Sonet', 'Carnival', 'Carens'],
        'FORD': ['EcoSport', 'Figo', 'Aspire', 'Endeavour'],
        'RENAULT': ['Kwid', 'Triber', 'Kiger', 'Duster'],
        'VOLKSWAGEN': ['Polo', 'Vento', 'Taigun', 'Tiguan'],
        'SKODA': ['Kushaq', 'Slavia', 'Octavia', 'Superb']
    }
    
    if make in indian_models:
        return jsonify({'models': indian_models[make]})
    else:
        return jsonify({'models': ['Base', 'Standard', 'Deluxe', 'Premium', 'Sport']})

@app.route('/api/vehicle-lookup', methods=['POST'])
@login_required
def vehicle_lookup():
    data = request.json
    registration = data.get('registration', '').strip().upper()
    
    if not registration:
        return jsonify({'error': 'Registration number is required'})
    
    try:
        # For Indian vehicles, we would use the VAHAN API in a production environment
        # Since we need an open-source API, we'll simulate a response based on the registration
        # In a real implementation, you would use a proper vehicle data API like VAHAN
        
        # Indian registration format validation (simplified)
        # Format: AA00AA0000 (State Code, District Code, Series, Number)
        if not re.match(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$', registration):
            return jsonify({'error': 'Invalid Indian registration format. Expected format: MH02AB1234'})
        
        # Extract state code to determine region
        state_code = registration[:2]
        
        # Map state codes to states
        state_map = {
            'AP': 'Andhra Pradesh',
            'AR': 'Arunachal Pradesh',
            'AS': 'Assam',
            'BR': 'Bihar',
            'CG': 'Chhattisgarh',
            'GA': 'Goa',
            'GJ': 'Gujarat',
            'HR': 'Haryana',
            'HP': 'Himachal Pradesh',
            'JK': 'Jammu and Kashmir',
            'JH': 'Jharkhand',
            'KA': 'Karnataka',
            'KL': 'Kerala',
            'MP': 'Madhya Pradesh',
            'MH': 'Maharashtra',
            'MN': 'Manipur',
            'ML': 'Meghalaya',
            'MZ': 'Mizoram',
            'NL': 'Nagaland',
            'OD': 'Odisha',
            'PB': 'Punjab',
            'RJ': 'Rajasthan',
            'SK': 'Sikkim',
            'TN': 'Tamil Nadu',
            'TS': 'Telangana',
            'TR': 'Tripura',
            'UK': 'Uttarakhand',
            'UP': 'Uttar Pradesh',
            'WB': 'West Bengal',
            'AN': 'Andaman and Nicobar Islands',
            'CH': 'Chandigarh',
            'DN': 'Dadra and Nagar Haveli',
            'DD': 'Daman and Diu',
            'DL': 'Delhi',
            'LD': 'Lakshadweep',
            'PY': 'Puducherry'
        }
        
        state = state_map.get(state_code, 'Unknown')
        
        # Use registration to deterministically select make and model
        # This is just for demo purposes - in production, use a real API
        
        # Popular car makes in India
        makes = ['MARUTI SUZUKI', 'TATA', 'MAHINDRA', 'HYUNDAI', 'HONDA', 'TOYOTA', 'KIA']
        
        # Models by make
        models = {
            'MARUTI SUZUKI': ['Swift', 'Baleno', 'Dzire', 'Ertiga', 'Brezza', 'Alto', 'Wagon R'],
            'TATA': ['Nexon', 'Harrier', 'Safari', 'Tiago', 'Altroz', 'Punch', 'Tigor'],
            'MAHINDRA': ['Scorpio', 'XUV700', 'XUV300', 'Thar', 'Bolero', 'Marazzo'],
            'HYUNDAI': ['Creta', 'i20', 'Venue', 'i10', 'Verna', 'Tucson', 'Alcazar'],
            'HONDA': ['City', 'Amaze', 'WR-V', 'Jazz', 'Civic'],
            'TOYOTA': ['Innova', 'Fortuner', 'Glanza', 'Urban Cruiser', 'Camry'],
            'KIA': ['Seltos', 'Sonet', 'Carnival', 'Carens']
        }
        
        # Use registration to deterministically select make and model
        make_index = sum(ord(c) for c in registration) % len(makes)
        make = makes[make_index]
        
        model_index = sum(ord(c) for c in registration) % len(models[make])
        model = models[make][model_index]
        
        # Generate a year between 2010 and 2023 based on registration
        year = 2010 + (sum(ord(c) for c in registration) % 14)
        
        return jsonify({
            'make': make,
            'model': model,
            'year': year,
            'additionalInfo': f'Vehicle registered in {state}'
        })
    
    except Exception as e:
        print(f"Error in vehicle lookup: {e}")
        return jsonify({'error': 'Failed to lookup vehicle details'})

@app.route('/upload_tuned/<submission_id>', methods=['GET', 'POST'])
@login_required
def upload_tuned(submission_id):
    if not current_user.is_admin:
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    submissions = get_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    
    if not submission:
        flash('Submission not found')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'tuned_file' not in request.files:
            flash('Tuned file is required')
            return redirect(request.url)
        
        tuned_file = request.files['tuned_file']
        
        if tuned_file.filename == '':
            flash('Tuned file is required')
            return redirect(request.url)
        
        tuned_filename = secure_filename(tuned_file.filename)
        tuned_blob = save_file_to_azure(tuned_file, tuned_filename, submission_id)
        
        # Update submission
        update_submission(submission_id, {
            'blob': tuned_blob,
            'filename': tuned_filename
        })
        
        flash('Tuned file uploaded successfully')
        return redirect(url_for('dashboard'))
    
    return render_template('upload_tuned.html', submission=submission)

@app.route('/download/<submission_id>/<file_type>')
@login_required
def download(submission_id, file_type):
    submissions = get_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    
    if not submission:
        flash('Submission not found')
        return redirect(url_for('dashboard'))
    
    if file_type == 'original':
        blob_name = submission['original_file']
        filename = submission['original_filename']
    elif file_type == 'tuned':
        if not submission.get('tuned_file'):
            flash('Tuned file not available')
            return redirect(url_for('dashboard'))
        blob_name = submission['tuned_file']['blob']
        filename = submission['tuned_file']['filename']
    elif file_type == 'image':
        blob_name = submission['vehicle_image']
        filename = submission['image_filename']
    else:
        flash('Invalid file type')
        return redirect(url_for('dashboard'))
    
    file_path = get_file_from_azure(blob_name)
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/submission/<submission_id>')
@login_required
def view_submission_details(submission_id):
    submissions = get_submissions()
    submission = next((s for s in submissions if s['id'] == submission_id), None)
    
    if not submission:
        flash('Submission not found')
        return redirect(url_for('dashboard'))
    
    # Find other submissions with the same registration number
    submissions_with_same_reg = []
    if submission.get('registration_number'):
        submissions_with_same_reg = [s for s in submissions 
                                    if s.get('registration_number') == submission.get('registration_number')]
    
    return render_template('submission_details.html', 
                          submission=submission,
                          submissions_with_same_reg=submissions_with_same_reg)

@app.route('/delete/<submission_id>', methods=['POST'])
@login_required
def delete_submission_route(submission_id):
    if not current_user.is_superadmin:
        flash('Access denied. Only superadmins can delete records.')
        return redirect(url_for('dashboard'))
    
    delete_submission(submission_id)
    flash('Submission deleted successfully')
    return redirect(url_for('dashboard'))

# Configure logging
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
else:
    if not app.debug:
        file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('DnD Autos ECU Remap Portal startup')

if __name__ == '__main__':
    app.run(debug=True, port=5001)