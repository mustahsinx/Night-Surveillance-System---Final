import cv2
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re, os
from ultralytics import YOLO
import smtplib
from email.message import EmailMessage
from enhancement import enhance_image
import threading
import time

# Initialize YOLOv8 model
model = YOLO("yolov8n.pt")  # yolov8n, yolov8m, yolov8l, yolov8x

# Global variables for motion detection
prev_frame = None
motion_detected = False

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/videos'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}
app.config['IMAGE_UPLOAD_FOLDER'] = 'static/images/uploads'
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# MySQL config (UPDATED ✅)
app.secret_key = 'supersecretkey'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'                 
app.config['MYSQL_PASSWORD'] = 'Hassan@29212'     
app.config['MYSQL_DB'] = 'nss'
mysql = MySQL(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_IMAGE_EXTENSIONS']


# Motion detection
def motion_detection(frame1, frame2):
    global motion_detected
    diff = cv2.absdiff(frame1, frame2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 20, 255, cv2.THRESH_BINARY)
    dilated = cv2.dilate(thresh, None, iterations=3)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = len(contours) > 0


def detect_objects_and_classify(frame):
    results = model(frame)
    desired_classes = ["person", "car", "motorcycle", "bicycle", "bus", "truck"]

    for detection in results[0].boxes:
        x1, y1, x2, y2 = map(int, detection.xyxy[0])
        conf = float(detection.conf[0])
        cls = int(detection.cls[0])
        class_name = model.names[cls]
        label = f"{class_name} {conf:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        if class_name in desired_classes:
            att = 'static/images/detected_frame.jpg'
            cv2.imwrite(att, frame)

            subject = "Motion Detected!"
            to = "user.nightshield@gmail.com"
            body = f"Motion of {class_name} detected by Night Surveillance System."
            threading.Thread(target=send_email_alert, args=(subject, body, to, att)).start()

    return frame


last_alert_time = 0


def send_email_alert(subject, body, to, att):
    global last_alert_time
    current_time = time.time()
    if current_time - last_alert_time < 50:
        print("⏳ Email alert skipped (rate limited).")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['subject'] = subject
    msg['to'] = to

    user = "mustahsinx@gmail.com"
    msg['from'] = user
    password = "Hassan@29212"   # ⚠️ App password hona chahiye Gmail ka

    try:
        with open(att, 'rb') as img_file:
            img_data = img_file.read()
            msg.add_attachment(img_data, maintype='image',
                               subtype='jpeg', filename='detected_frame.jpg')

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        last_alert_time = current_time
        print("✅ Email alert sent!")
    except Exception as e:
        print(f"❌ Email send error: {e}")


def video_stream(source, stop_event):
    global prev_frame, motion_detected
    cap = cv2.VideoCapture(source)

    ret, prev_frame = cap.read()
    if not ret:
        print("❌ Could not read initial frame.")
        return

    prev_frame = cv2.resize(prev_frame, (640, 480))

    while not stop_event.is_set() and cap.isOpened():
        try:
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.resize(frame, (640, 480))
            frame_bytes = b''

            if prev_frame is not None:
                motion_detection(prev_frame, frame)
                if motion_detected:
                    enhanced_frame = enhance_image(frame)
                    detected_frame = detect_objects_and_classify(enhanced_frame)
                    _, jpeg = cv2.imencode('.jpg', detected_frame)
                    frame_bytes = jpeg.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   frame_bytes + b'\r\n')

            if motion_detected:
                prev_frame = frame.copy()
        except Exception as e:
            print(f"⚠️ Stream error: {e}")
            break

    cap.release()


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/upload', methods=['GET'])
def upload():
    video_path = request.args.get('video_path')
    return render_template('upload_video.html', video_path=video_path)


@app.route('/upload_video', methods=['GET', 'POST'])
def upload_video():
    if request.method == 'POST':
        if 'video' not in request.files:
            return 'No video file uploaded'
        video = request.files['video']
        if video.filename == '':
            return 'No video file selected'
        if video and allowed_file(video.filename):
            filename = video.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            video.save(file_path)
            return redirect(url_for('upload', video_path=file_path))
        return 'Invalid File Type'
    return render_template('upload_video.html')


@app.route('/upload_video_feed')
def upload_video_feed():
    video_path = request.args.get('video_path')
    if video_path:
        stop_event = threading.Event()
        return Response(video_stream(video_path, stop_event),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    return 'No video path provided'


@app.route('/upload_image', methods=['GET', 'POST'])
def upload_image():
    """Upload an image, run enhancement, and show original + enhanced preview."""
    error = None
    original_url = None
    enhanced_url = None

    if request.method == 'POST':
        if 'image' not in request.files:
            error = 'No image file uploaded'
            return render_template('enhance_image.html', error=error)

        image = request.files['image']
        if image.filename == '':
            error = 'No image selected'
            return render_template('enhance_image.html', error=error)

        if image and allowed_image(image.filename):
            filename = secure_filename(image.filename)

            # Ensure upload directories exist
            upload_dir = os.path.join(app.static_folder, 'images', 'uploads')
            enhanced_dir = os.path.join(app.static_folder, 'images', 'enhanced')
            os.makedirs(upload_dir, exist_ok=True)
            os.makedirs(enhanced_dir, exist_ok=True)

            save_path = os.path.join(upload_dir, filename)
            image.save(save_path)

            # Read with OpenCV, enhance, and save enhanced image
            try:
                img = cv2.imread(save_path)
                if img is None:
                    raise ValueError('Uploaded file cannot be read as an image')

                enhanced = enhance_image(img)
                enhanced_filename = os.path.splitext(filename)[0] + '_enhanced.jpg'
                enhanced_path = os.path.join(enhanced_dir, enhanced_filename)
                cv2.imwrite(enhanced_path, enhanced)

                original_url = url_for('static', filename=f'images/uploads/{filename}')
                enhanced_url = url_for('static', filename=f'images/enhanced/{enhanced_filename}')

                return render_template('enhance_image.html', original_url=original_url, enhanced_url=enhanced_url)
            except Exception as e:
                error = f'Image processing error: {e}'
                return render_template('enhance_image.html', error=error)
        else:
            error = 'Invalid image file type'
            return render_template('enhance_image.html', error=error)

    return render_template('enhance_image.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    mesage = ''
    if request.method == 'POST' and 'firstname' in request.form and 'password' in request.form:
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        password = request.form['password']
        email = request.form['email']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM user WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account:
            mesage = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            mesage = 'Invalid email address!'
        elif not firstname or not password or not email:
            mesage = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO user (firstname, lastname, email, password) VALUES (%s, %s, %s, %s)',
                           (firstname, lastname, email, password))
            mysql.connection.commit()
            mesage = '✅ Registration successful!'
    elif request.method == 'POST':
        mesage = 'Please fill out the form!'
    return render_template('home.html', mesage=mesage)


@app.route('/login', methods=['GET', 'POST'])
def login():
    mesage = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            'SELECT * FROM user WHERE email = %s AND password = %s', (email, password,))
        user = cursor.fetchone()
        if user:
            session['loggedin'] = True
            session['sno'] = user['sno']
            session['firstname'] = user['firstname']
            session['email'] = user['email']
            return render_template('dashboard.html', mesage='Welcome back!')
        else:
            mesage = 'Incorrect email or password!'
    return render_template('home.html', mesage=mesage)


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/addCamera')
def addCamera():
    return render_template('addCamera.html')


@app.route('/cam', methods=['GET', 'POST'])
def cam():
    mesage = ''
    if request.method == 'POST' and 'camname' in request.form and 'camurl' in request.form:
        camname = request.form['camname']
        camurl = request.form['camurl']
        camfps = request.form['camfps']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM cam WHERE camname = %s', (camname,))
        account = cursor.fetchone()

        if account:
            mesage = 'Camera already exists!'
        elif not camfps or not camurl or not camname:
            mesage = 'Please fill out the form!'
        else:
            cursor.execute(
                'INSERT INTO cam (camfps, camurl, camname) VALUES (%s, %s, %s)',
                (camfps, camurl, camname))
            mysql.connection.commit()
            mesage = '✅ Camera added!'
    elif request.method == 'POST':
        mesage = 'Please fill out the form!'
    return render_template('dashboard.html', mesage=mesage)


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/night-shield-legal')
def night_shield_legal():
    return render_template('night-shield-legal.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route('/video_feed')
def video_feed():
    stop_event = threading.Event()
    return Response(video_stream(0, stop_event),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)
