from flask import Flask, render_template, request, jsonify
from PIL import Image
from pyzbar import pyzbar
import cv2
import numpy as np
import re
try:
    import zxingcpp
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False

app = Flask(__name__)

def parse_dl_data(raw_data):
    """Parse ANSI driver's license data into readable format"""
    parsed = {}
    
    # Decode HTML entities and control characters
    import html
    decoded_data = html.unescape(raw_data)
    decoded_data = decoded_data.replace('<LF>', '\n').replace('<RS>', '\x1e').replace('<CR>', '\r')
    
    print(f"Decoded data: {decoded_data[:200]}...")
    
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
        'DDG': 'Middle Name Truncated'
    }
    
    # Split by line feed and parse each field
    lines = decoded_data.replace('\r', '').split('\n')
    
    for line in lines:
        if len(line) >= 3:
            field_code = line[:3]
            field_value = line[3:].strip()
            
            if field_code in field_map and field_value:
                parsed[field_map[field_code]] = field_value
                print(f"Found field: {field_code} -> {field_map[field_code]}: {field_value}")
    
    return parsed

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan_barcode():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    
    try:
        pil_image = Image.open(file.stream)
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        h, w = cv_image.shape[:2]
        
        print(f"Image size: {w}x{h}")
        
        # Define fixed PDF417 scan area
        box_width = int(w * 0.7)
        box_height = int(h * 0.15)
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
                
                # Try without format restriction first, then with PDF417 only
                results = zxingcpp.read_barcodes(gray_area)
                
                print(f"ZXing found {len(results)} barcodes")
                
                for result in results:
                    if result.valid and 'PDF417' in str(result.format):
                        decoded_data = result.text
                        # Parse the ANSI driver's license data
                        parsed_data = parse_dl_data(decoded_data)
                        
                        print(f"SUCCESS! ZXing decoded PDF417: {decoded_data[:100]}...")
                        print("\n=== PARSED DRIVER'S LICENSE DATA ===")
                        for key, value in parsed_data.items():
                            print(f"{key}: {value}")
                        print("=====================================\n")
                        
                        cv2.rectangle(annotated_image, (box_left, box_top), (box_left + box_width, box_top + box_height), (0, 255, 0), 3)
                        cv2.putText(annotated_image, "PDF417 (ZXing)", (box_left, box_top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
                        cv2.imwrite('annotated_image.jpg', annotated_image)
                        return jsonify({
                            'success': True, 
                            'data': parsed_data,
                            'raw_data': decoded_data,
                            'method': 'ZXing-CPP'
                        })
                        
            except Exception as e:
                print(f"ZXing failed: {e}")
        
        # Try OpenCV barcode detector
        try:
            detector = cv2.barcode.BarcodeDetector()
            retval, decoded_info, decoded_type = detector.detectAndDecode(pdf417_area)
            
            print(f"OpenCV detector found: {len(decoded_info) if decoded_info else 0} barcodes")
            
            if decoded_info:
                for i, (info, barcode_type) in enumerate(zip(decoded_info, decoded_type)):
                    if info and 'PDF417' in str(barcode_type):
                        print(f"SUCCESS! OpenCV decoded PDF417: {info[:100]}...")
                        cv2.imwrite('annotated_image.jpg', annotated_image)
                        return jsonify({
                            'success': True, 
                            'data': info,
                            'method': 'OpenCV'
                        })
        except Exception as e:
            print(f"OpenCV detector failed: {e}")
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
                print(f"pyzbar {name}: Found {len(barcodes)} barcodes")
                
                for barcode in barcodes:
                    if barcode.type == 'PDF417':
                        x, y, w_bar, h_bar = barcode.rect
                        x += box_left
                        y += box_top
                        
                        cv2.rectangle(annotated_image, (x, y), (x + w_bar, y + h_bar), (0, 255, 0), 2)
                        cv2.putText(annotated_image, f"PDF417 ({name})", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                        
                        decoded_data = barcode.data.decode('utf-8')
                        print(f"SUCCESS! pyzbar {name} decoded PDF417: {decoded_data[:100]}...")
                        cv2.imwrite('annotated_image.jpg', annotated_image)
                        return jsonify({
                            'success': True, 
                            'data': decoded_data,
                            'method': f'pyzbar {name}'
                        })
                        
            except Exception as e:
                print(f"pyzbar {name} failed: {e}")
        
        return jsonify({
            'success': False, 
            'message': 'PDF417 visible in scan area but not decoded by any method.',
            'zxing_available': ZXING_AVAILABLE
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)