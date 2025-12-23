from flask import Flask, render_template, request, jsonify
from PIL import Image
from pyzbar import pyzbar
import cv2
import numpy as np
import re
import base64
from datetime import datetime
import json
import os
try:
    import zxingcpp
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False

app = Flask(__name__)

# Persistent scan counter
STATS_FILE = 'scan_stats.json'

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {'scan_count': 0, 'last_scans': []}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def parse_dl_data(raw_data):
    """Parse ANSI driver's license data into readable format"""
    parsed = {}
    
    # Decode HTML entities and control characters
    import html
    decoded_data = html.unescape(raw_data)
    decoded_data = decoded_data.replace('<LF>', '\n').replace('<RS>', '\x1e').replace('<CR>', '\r')
    
    # Common ANSI field mappings
    field_map = {
        'DCS': 'Last Name',
        'DCT': 'First Name', 
        'DAC': 'First Name',
        'DBD': 'Issue Date',
        'DBA': 'Expiration Date',
        'DBB': 'Date of Birth',
        'DBC': 'Sex',
        'DAY': 'Eye Color',
        'DAU': 'Height',
        'DAG': 'Address',
        'DAI': 'City',
        'DAJ': 'State',
        'DAK': 'ZIP Code',
        'DAQ': 'License Number',
        'DCG': 'Country',
        'DDE': 'Last Name Truncated',
        'DDF': 'First Name Truncated',
        'DDG': 'Middle Name Truncated',
        'DAD': 'Middle Name',
        'DCF': 'Document Discriminator',
        'DCJ': 'Audit Information'
    }
    
    # Remove DL prefix and split by field codes using regex
    decoded_data = decoded_data.replace('\r', '').replace('\x1e', '\n')
    
    # Find all field codes and their values using regex
    pattern = r'(D[A-Z]{2})([^D]*?)(?=D[A-Z]{2}|$)'
    matches = re.findall(pattern, decoded_data, re.DOTALL)
    
    for field_code, field_value in matches:
        field_value = field_value.strip()
        if field_code in field_map and field_value:
            parsed[field_map[field_code]] = field_value
    
    return parsed

def increment_scan_count():
    stats = load_stats()
    stats['scan_count'] += 1
    stats['last_scans'].append(datetime.now().isoformat())
    stats['last_scans'] = stats['last_scans'][-3:]  # Keep only last 3
    save_stats(stats)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan-stats')
def scan_stats():
    stats = load_stats()
    return jsonify({
        'total_scans': stats['scan_count'],
        'last_scans': stats['last_scans']
    })

@app.route('/scan', methods=['POST'])
def scan_barcode():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    
    try:
        pil_image = Image.open(file.stream)
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        h, w = cv_image.shape[:2]
        
        # Define fixed PDF417 scan area
        box_width = int(w * (int(request.form.get('box_width', 70)) / 100))
        box_height = int(h * (int(request.form.get('box_height', 15)) / 100))
        box_left = int((w - box_width) / 2)
        box_top = int((h - box_height) / 2)  # Center vertically
        
        pdf417_area = cv_image[box_top:box_top + box_height, box_left:box_left + box_width]
        
        annotated_image = cv_image.copy()
        cv2.rectangle(annotated_image, (box_left, box_top), (box_left + box_width, box_top + box_height), (0, 255, 0), 3)
        cv2.putText(annotated_image, "PDF417 Scan Area", (box_left, box_top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        all_detected = []
        
        # Try ZXing-CPP first (excellent PDF417 support)
        if ZXING_AVAILABLE:
            try:
                # Convert to grayscale for zxing
                gray_area = cv2.cvtColor(pdf417_area, cv2.COLOR_BGR2GRAY)
                
                results = zxingcpp.read_barcodes(gray_area)
                
                for result in results:
                    if result.valid and 'PDF417' in str(result.format):
                        decoded_data = result.text
                        parsed_data = parse_dl_data(decoded_data)
                        
                        cv2.rectangle(annotated_image, (box_left, box_top), (box_left + box_width, box_top + box_height), (0, 255, 0), 3)
                        cv2.putText(annotated_image, "PDF417 (ZXing)", (box_left, box_top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
                        _, buffer = cv2.imencode('.jpg', annotated_image)
                        image_base64 = base64.b64encode(buffer).decode('utf-8')
                        
                        increment_scan_count()
                        return jsonify({
                            'success': True, 
                            'data': parsed_data,
                            'raw_data': decoded_data,
                            'method': 'ZXing-CPP',
                            'image_base64': image_base64
                        })
                        
            except Exception as e:
                pass
        
        # Try OpenCV barcode detector
        try:
            detector = cv2.barcode.BarcodeDetector()
            retval, decoded_info, decoded_type = detector.detectAndDecode(pdf417_area)
            
            if decoded_info:
                for i, (info, barcode_type) in enumerate(zip(decoded_info, decoded_type)):
                    if info and 'PDF417' in str(barcode_type):
                        increment_scan_count()
                        return jsonify({
                            'success': True, 
                            'data': info,
                            'method': 'OpenCV'
                        })
        except Exception as e:
            pass
        processing_methods = [
            ('Original', pdf417_area),
            ('Gray', cv2.cvtColor(pdf417_area, cv2.COLOR_BGR2GRAY)),
            ('Binary', cv2.threshold(cv2.cvtColor(pdf417_area, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
            ('Inverted', 255 - cv2.threshold(cv2.cvtColor(pdf417_area, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
            ('Dilated', cv2.dilate(cv2.threshold(cv2.cvtColor(pdf417_area, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1], np.ones((2,2), np.uint8), iterations=1)),
        ]
        
        for name, img in processing_methods:
            try:
                barcodes = pyzbar.decode(img)
                
                for barcode in barcodes:
                    if barcode.type == 'PDF417':
                        x, y, w_bar, h_bar = barcode.rect
                        x += box_left
                        y += box_top
                        
                        cv2.rectangle(annotated_image, (x, y), (x + w_bar, y + h_bar), (0, 255, 0), 2)
                        cv2.putText(annotated_image, f"PDF417 ({name})", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                        
                        decoded_data = barcode.data.decode('utf-8')
                        parsed_data = parse_dl_data(decoded_data)
                        
                        _, buffer = cv2.imencode('.jpg', annotated_image)
                        image_base64 = base64.b64encode(buffer).decode('utf-8')
                        
                        increment_scan_count()
                        return jsonify({
                            'success': True, 
                            'data': parsed_data,
                            'raw_data': decoded_data,
                            'method': f'pyzbar {name}',
                            'image_base64': image_base64
                        })
                        
            except Exception as e:
                pass
        
        return jsonify({
            'success': False, 
            'message': 'PDF417 visible in scan area but not decoded by any method.',
            'zxing_available': ZXING_AVAILABLE
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(debug=True, port=port)