import os
import time
import logging
from flask import Flask, render_template, request, send_from_directory, jsonify, abort
from werkzeug.utils import secure_filename
from utils.converters import convert_file, get_supported_conversions

app = Flask(__name__, template_folder='.')

# Configuration
UPLOAD_FOLDER = os.path.abspath('uploads')
CONVERTED_FOLDER = os.path.abspath('converted')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB limit
CLEANUP_THRESHOLD = 600  # Delete files older than 10 minutes

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)

def cleanup_old_files():
    """Remove files older than CLEANUP_THRESHOLD from uploads and converted folders."""
    now = time.time()
    for folder in [UPLOAD_FOLDER, CONVERTED_FOLDER]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                if now - os.path.getmtime(filepath) > CLEANUP_THRESHOLD:
                    try:
                        os.remove(filepath)
                        logging.info(f"Deleted old file: {filename}")
                    except Exception as e:
                        logging.error(f"Error deleting {filename}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    cleanup_old_files() # opportunistic cleanup
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        # Preserve extension for detection
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Get supported conversions
        name, ext = os.path.splitext(filename)
        supported_formats = get_supported_conversions(ext)
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename,
            'supported_formats': supported_formats
        })

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    filename = data.get('filename')
    target_format = data.get('format')
    
    if not filename or not target_format:
        return jsonify({'error': 'Missing filename or target format'}), 400
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(input_path):
        return jsonify({'error': 'File not found (expired?). Please upload again.'}), 404
        
    try:
        output_path = convert_file(input_path, app.config['CONVERTED_FOLDER'], target_format)
        output_filename = os.path.basename(output_path)
        
        # Optionally remove original upload immediately to save space
        try:
             os.remove(input_path)
        except:
             pass

        return jsonify({
            'message': 'Conversion successful',
            'download_url': f"/download/{output_filename}"
        })
    except Exception as e:
        logging.error(f"Conversion error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['CONVERTED_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=3000) # Running on 3000 to avoid conflicts
