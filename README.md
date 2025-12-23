# Driver's License Scanner

A real-time web application that scans and decodes PDF417 barcodes on driver's licenses using computer vision and multiple barcode detection libraries.

## How It Works

### Barcode Detection Process

1. **Camera Feed**: Captures live video from selected camera
2. **Scan Area**: Defines a centered rectangular region (70% width × 15% height) for PDF417 detection
3. **Multi-Library Approach**: Uses multiple detection methods in priority order:
   - **ZXing-CPP**: Primary decoder with excellent PDF417 support
   - **OpenCV**: Backup barcode detector
   - **pyzbar**: Fallback with multiple image preprocessing techniques

### ANSI Data Parsing

The PDF417 barcode contains ANSI-encoded driver's license data with standardized field codes:
- `DCS`: Last Name
- `DCT`/`DAC`: First Name  
- `DBD`: Issue Date
- `DBA`: Expiration Date
- `DBB`: Date of Birth
- `DBC`: Sex
- `DAY`: Eye Color
- `DAU`: Height
- `DAG`: Address
- `DAI`: City
- `DAJ`: State
- `DAK`: ZIP Code
- `DAQ`: License Number

### Image Processing Pipeline

For each frame, the system:
1. Extracts the defined scan area
2. Applies multiple preprocessing techniques (grayscale, binary threshold, morphological operations)
3. Attempts barcode detection with each method
4. Parses successful reads into human-readable format
5. Returns both prettified data and raw barcode content

## Setup

### Prerequisites

- Python 3.7+
- Webcam or camera device (iPhone or high-quality cameras recommended for dense PDF417 barcodes)
- Modern web browser with camera permissions

### Installation

1. **Clone/Download** the project files

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Optional: Install ZXing-CPP** (recommended for better PDF417 detection):
```bash
pip install zxing-cpp
```

### Requirements File Contents

```
Flask==2.3.3
opencv-python==4.8.1.78
pyzbar==0.1.9
Pillow==10.0.1
numpy==1.24.3
```

## Usage

### Privacy & Statistics

**Important:** This scanner tracks successful scans for statistical purposes only. Each successful scan increments a counter that can be accessed via the `/scan-stats` API endpoint. No personal data from licenses is stored - only scan counts and timestamps are recorded.

### Starting the Application

```bash
sudo apt-get install libzbar0 libzbar-dev
```

```bash
python app.py        # Default port 5000
python app.py 8080   # Custom port 8080
```

The server starts at `http://localhost:5000` (or your specified port)

### Scanning Process

1. **Select Camera**: Choose from available cameras in the dropdown
2. **Start Camera**: Click "Start Camera" to begin video feed
3. **Customize Overlay**: Adjust box width/height percentages or use URL parameters (`?width=80&height=20`)
4. **Position License**: Place driver's license so the back barcode is within the green alignment box
5. **Automatic Scanning**: The app continuously scans every second
6. **Results**: When successful, displays:
   - Annotated image showing detected barcode area
   - Prettified license information (copy-pasteable)
   - Collapsible raw barcode data with copy button
   - Download option for annotated image

### Tips for Best Results

- **Camera Quality**: Use iPhone or high-quality cameras - PDF417 barcodes contain dense information requiring good resolution
- **Lighting**: Ensure even, bright lighting without shadows or glare
- **Positioning**: Keep the PDF417 barcode fully within the green box
- **Orientation**: Use the flip camera button if the barcode appears mirrored
- **Stability**: Hold the license steady during scanning
- **Distance**: Maintain appropriate distance for clear barcode visibility
- **Angle**: Keep the license flat and parallel to the camera

### Features

- **Real-time Detection**: Continuous scanning without manual capture
- **Multiple Decoders**: Fallback detection methods for reliability
- **Camera Controls**: Flip camera orientation for better positioning
- **Scan Statistics**: Persistent counter tracking successful scans
- **Data Export**: Copy prettified or raw data to clipboard
- **Image Download**: Save annotated scan results
- **Responsive Design**: Works on desktop and mobile browsers
- **Security**: No server-side file storage, base64 image embedding
- **Privacy**: Only scan statistics stored, no personal data retention
- **Session Management**: Automatic idle user redirection to prevent resource consumption

### Troubleshooting

**No Detection**:
- Improve lighting conditions
- Ensure barcode is within green alignment box
- Try different camera angles
- Check if ZXing-CPP is installed for better detection

**Camera Issues**:
- Grant camera permissions in browser
- Try different cameras from the dropdown
- Refresh page and restart camera

**Poor Image Quality**:
- Clean camera lens
- Increase lighting
- Reduce camera shake
- Move closer/farther for optimal focus

## Technical Details

- **Backend**: Flask web server with persistent scan statistics
- **Computer Vision**: OpenCV for image processing
- **Barcode Libraries**: ZXing-CPP, pyzbar, OpenCV barcode detector
- **Frontend**: Vanilla JavaScript with WebRTC camera access
- **Data Storage**: JSON file for scan counter persistence
- **Security**: Client-side image handling, no server file storage