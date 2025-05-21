from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import firebase_admin
from firebase_admin import credentials, firestore
from flask_mail import Mail, Message
import random
import logging
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Flask-Mail configuration (update with your SMTP server details)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'programmingsir999@gmail.com'
app.config['MAIL_PASSWORD'] = 'gxkzdrtpoasutbns'
mail = Mail(app)

# File upload config
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_otp(email, username):
    otp = random.randint(100000, 999999)
    msg = Message(
        subject="OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f"Hello {username}, your OTP is {otp}"
    try:
        mail.send(msg)
        return otp
    except Exception as e:
        logging.error(f"Error sending OTP: {e}")
        return None

# Initialize Firebase (add this after your imports and before routes)
try:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    db = None
    logging.error(f"Firebase initialization failed: {e}")

@app.route('/')
def home():
    return render_template('teacher.html')

@app.route('/teacher-login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Store teacher info in Firestore 'teacher' collection using username as document ID
        if db:
            try:
                db.collection('teacher').document(username).set({
                    'email': email,
                    'username': username,
                    'password': password
                })
                logging.info(f"Teacher info stored: {email}, {username}")
            except Exception as e:
                logging.error(f"Error saving teacher info: {e}")
                flash("Failed to save teacher info to database.")
        else:
            flash("Database not initialized. Please check your Firebase credentials.")

        # Send OTP and store in session
        otp = send_otp(email, username)
        if otp:
            session['otp'] = str(otp)
            flash("OTP sent to your email address.")
        else:
            flash("Failed to send OTP. Please check your email configuration and try again.")
            return render_template('teacher_login.html')

        session['email'] = email
        session['username'] = username
        session['password'] = password
        return redirect(url_for('verify_otp'))
    return render_template('teacher_login.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == session.get('otp'):
            flash("OTP verified successfully!")
            # Optionally clear OTP from session
            session.pop('otp', None)
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid OTP. Please try again.")
            return render_template('verify_otp.html')
    return render_template('verify_otp.html')

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('email')
    username = session.get('username')
    if not email or not username:
        flash("Session expired. Please login again.")
        return redirect(url_for('teacher_login'))
    otp = send_otp(email, username)
    if otp:
        session['otp'] = str(otp)
        flash("OTP resent to your email address.")
    else:
        flash("Failed to resend OTP. Please check your email configuration and try again.")
    return redirect(url_for('verify_otp'))

@app.route('/admin-dashboard')
def admin_dashboard(): 
    return render_template('admin_dashboard.html',)


@app.route('/add-students', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form.get('name')
        user_id = request.form.get('id')
        email = request.form.get('email')

        if not name or not user_id:
            return "Name and ID both are required.", 400

        if db:
            db.collection('users').document(user_id).set({
                'name': name,
                'Student_id': user_id,
                'email': email
            })
            return redirect(url_for('success'))
        else:
            return "Database not initialized. Please check your Firebase credentials.", 500

    return render_template('form.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/total-students', methods=['GET', 'POST'])
def total_students():
    if request.method == 'POST':
        student_id = request.form.get('delete_id')
        if db and student_id:
            try:
                db.collection('users').document(student_id).delete()
                flash("Student deleted successfully.")
            except Exception as e:
                logging.error(f"Error deleting student: {e}")
                flash("Failed to delete student.")
        return redirect(url_for('total_students'))

    students_list = []
    if db:
        try:
            users = db.collection('users').stream()
            for user in users:
                data = user.to_dict()
                data['student_id'] = user.id
                students_list.append(data)
        except Exception as e:
            logging.error(f"Error fetching students: {e}")
            flash("Failed to fetch students.")
    else:
        flash("Database connection failed.")
    return render_template('total_students.html', students=students_list)



@app.route('/Notification', methods=['GET', 'POST'])
def Notification():
    message = None
    error = None
    if request.method == 'POST':
        notification = request.form.get('notification')
        attachment = request.files.get('attachment')
        attachment_url = None

        if attachment and allowed_file(attachment.filename):
            filename = secure_filename(attachment.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            attachment.save(file_path)
            attachment_url = f'/uploads/{filename}'  # This is a local path, not a Firebase URL

        if db and notification:
            try:
                data = {'text': notification}
                if attachment_url:
                    data['attachment_url'] = attachment_url
                db.collection('notifications').add(data)
                message = "Notification uploaded successfully."
            except Exception as e:
                error = f"Failed to upload notification: {e}"
        else:
            error = "Notification text is required and database must be connected."

    return render_template('Notification.html', message=message, error=error)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/all-notifications')
def all_notifications():
    notifications_list = []
    if db:
        try:
            notifications = db.collection('notifications').stream()
            for n in notifications:
                data = n.to_dict()
                notifications_list.append(data)
        except Exception as e:
            logging.error(f"Error fetching notifications: {e}")
            flash("Failed to fetch notifications.")
    else:
        flash("Database connection failed.")
    return render_template('all_notifications.html', notifications=notifications_list)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)

