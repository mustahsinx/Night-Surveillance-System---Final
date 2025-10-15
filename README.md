# Night Surveillance System

A lightweight Flask-based Night Surveillance System that performs motion detection, image enhancement, and object detection using YOLOv8. It provides a web UI to register/login users, add cameras, upload videos for processing, stream live webcam/video feeds, and upload images for enhancement.

---

## Features
- Motion detection on video streams (webcam or uploaded video).
- Object detection and annotation using Ultralytics YOLOv8 (weights included: `yolov8n.pt`).
- Email alerts with detected frames attached (SMTP via Gmail configured in `main.py`).
- Image enhancement endpoint to upload a photo and preview the enhanced result (uses `enhancement.py`).
- Simple user and camera management backed by a MySQL database (`nss`).

---

## Repo structure (important files)

```
Night Surveillance System - Final/
├─ main.py                 # Flask app + routing, motion detection, YOLO inference
├─ enhancement.py          # Image enhancement routine (CLAHE + gamma correction)
├─ yolov8n.pt              # YOLOv8 model weights (small)
├─ Query1.sql              # SQL to create `nss` database and required tables
├─ templates/              # Jinja2 HTML templates
│  ├─ home.html
│  ├─ dashboard.html
│  ├─ upload_video.html
│  ├─ preview.html
│  └─ enhance_image.html   # Image enhancement upload & preview page (added)
├─ static/                 # Static files (css, js, images, videos)
└─ README.md               # This file
```

---

## Prerequisites
- Python 3.10+ (3.11 / 3.13 tested in this workspace)
- MySQL or MariaDB server
- For object detection: `yolov8n.pt` is included. `ultralytics` will install required PyTorch/torch dependencies; choose CPU or GPU wheel accordingly for performance.

Python packages used (install with pip):
- flask
- flask-mysqldb
- mysqlclient
- ultralytics
- opencv-python
- scipy
- numpy
- (werkzeug is included with Flask)

If you prefer an easier Windows install for the DB connector, see the Troubleshooting section for switching to `PyMySQL`.

---

## Setup & Run (Windows PowerShell)

1) Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2) Upgrade pip and install dependencies:

```powershell
pip install --upgrade pip
pip install flask flask-mysqldb mysqlclient ultralytics opencv-python scipy numpy
```

Notes:
- `mysqlclient` sometimes needs Visual C++ Build Tools on Windows. If you get an error installing it, see the Troubleshooting section.
- `ultralytics` will pull a compatible `torch` wheel. If you have a GPU and want CUDA support, install a matching `torch` wheel first (see PyTorch docs) then install `ultralytics`.

3) Create the database and tables using the provided SQL:

```powershell
# will prompt for your MySQL root password
mysql -u root -p < "d:\Night Surveillance System - Final\Query1.sql"
```

Alternatively, in the MySQL client:

```sql
SOURCE "d:\\Night Surveillance System - Final\\Query1.sql";
```

4) (Optional) Update credentials and secrets in `main.py` or use environment variables:

Open `main.py` and check these settings and replace with your secure values:

```py
app.secret_key = 'supersecretkey'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'your_mysql_password'
app.config['MYSQL_DB'] = 'nss'

# Email (used to send alerts)
user = 'your_email@gmail.com'
password = 'your_email_app_password'
```

Security note: Do NOT keep plain secrets in source for production. Use environment variables or a secrets manager.

5) Start the server:

```powershell
python "d:\Night Surveillance System - Final\main.py"
```

6) Open the web UI in a browser:

- Home: http://127.0.0.1:5000/
- Live webcam feed: http://127.0.0.1:5000/video_feed
- Upload video: http://127.0.0.1:5000/upload_video
- Image enhancement page: http://127.0.0.1:5000/upload_image

---

## Routes (summary)

- GET `/` — Home (login/register)
- POST `/signup` — Register a user
- POST `/login` — Login
- GET `/dashboard` — Dashboard page
- GET `/addCamera` — Add camera UI
- POST `/cam` — Add camera to DB
- GET `/upload` — Upload video form
- POST `/upload_video` — Upload video file (saved to `static/videos/`)
- GET `/upload_video_feed?video_path=<path>` — Stream the uploaded video (multipart jpeg stream)
- GET `/video_feed` — Stream live webcam (device index 0)
- GET/POST `/upload_image` — New: upload an image to enhance and preview the original + enhanced images

---

## Image enhancement page (`/upload_image`)

How it works:
- Upload an image (png/jpeg/bmp/tiff) via the form on the page.
- The file is saved under `static/images/uploads/`.
- `enhancement.enhance_image()` reads the file using OpenCV and applies:
  - Median denoising (scipy.ndimage.median_filter)
  - CLAHE (contrast limited adaptive histogram equalization)
  - Simple gamma correction
- The enhanced image is saved to `static/images/enhanced/` with `_enhanced.jpg` suffix and both original and enhanced versions are shown in the browser.

Usage:
1. Visit http://127.0.0.1:5000/upload_image
2. Choose an image and click `Upload & Enhance`
3. Preview the results side-by-side

---

## Email alerts

- `main.py` will send email alerts when certain objects are detected (person, car, motorcycle, bicycle, bus, truck).
- The SMTP configuration in `main.py` currently uses Gmail SMTP (`smtp.gmail.com:587`).
- For Gmail, create an App Password for SMTP (strongly recommended) if your account has 2FA. Using regular Gmail password will likely fail.

---

## Troubleshooting

- mysqlclient installation errors on Windows:
  - Option A: Install Microsoft Visual C++ Build Tools (required for compiling C extensions).
  - Option B: Install `PyMySQL` instead and modify `main.py` to use it (I can change this for you — it's a small edit).
  - Option C: Use WSL/Ubuntu where `mysqlclient` is easier to install.

- Ultralytics / torch issues:
  - If `ultralytics` installs a slow CPU-only `torch`, performance will be limited. If you have an NVIDIA GPU, install the matching `torch` wheel with CUDA before installing `ultralytics`.

- OpenCV camera errors: If `/video_feed` does not show frames, make sure:
  - You have a webcam available and accessible by OpenCV.
  - No other program is exclusively locking the webcam.

- Email not sending:
  - Check SMTP credentials and allow less-restrictive app access (use App Password for Gmail).
  - Check network/firewall rules.

- Uploaded images not processed or blank preview:
  - Confirm upload file types and that `cv2.imread` returns a non-None image. If `imread` returns `None`, the file may be corrupted or an unsupported format.

---

## Security recommendations

- Move secrets out of `main.py` and into environment variables or a configuration file excluded from version control.
- Hash user passwords before saving to the DB (use `werkzeug.security.generate_password_hash` and `check_password_hash`). The current implementation stores plaintext passwords — change before production.
- Add file-size limits for uploads and validate MIME types.
- Run the Flask app behind a production WSGI server (gunicorn/uvicorn) and reverse-proxy (NGINX) for production deployments.

---

## Optional improvements / next steps

- Replace `flask_mysqldb` + `mysqlclient` with `PyMySQL` for easier cross-platform installs.
- Add a `requirements.txt` and a simple `Makefile` or PowerShell script for setup.
- Add password hashing and email confirmation for registration.
- Add Dockerfile + docker-compose for easier deployment (MySQL + app + optional GPU support).
- Add rate limiting and authentication for API endpoints.

---

If you want, I can:
- Generate a `requirements.txt` and lockfile.
- Replace DB connector to `PyMySQL` for simpler Windows installs and update the code.
- Add password hashing and a .env config support.

Tell me which of the above you'd like next and I'll implement it.

---

License: This project is provided as-is for development and learning purposes. Review and secure before production use.
