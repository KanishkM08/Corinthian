import os
import sys
import streamlit as st
import pandas as pd
from pathlib import Path
import uuid
from datetime import datetime

# Ensure "src" is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, os.path.abspath(src_dir))

# Add the dashboard directory to Python path
dashboard_dir = os.path.join(current_dir, '..')
sys.path.insert(0, os.path.abspath(dashboard_dir))

# Add current directory for local imports
sys.path.insert(0, current_dir)

# Imports with error handling
try:
    from src.metadata import log_evidence_from_path
except ImportError:
    st.error("Could not import src.metadata. Ensure src/metadata.py exists and path is correct.")
    st.stop()

# Import the PDF report generator
try:
    from generate_report import generate_report
except ImportError:
    st.error("Could not import generate_report. Ensure generate_report.py is alongside app.py.")
    st.stop()

# File selection functions
def get_file_mac(file_type="cctv"):
    import subprocess
    if file_type == "excel":
        prompt = "Select an Excel file"
        file_types = '{"xlsx", "xls"}'
    else:
        prompt = "Select a CCTV file"
        file_types = '{"jpeg", "jpg", "png", "mov", "mp4", "avi", "heic"}'
    script = f'''
    set chosenFile to POSIX path of (choose file with prompt "{prompt}" of type {file_types})
    return chosenFile
    '''
    proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if proc.returncode == 0:
        return proc.stdout.strip()
    return None

def get_file_others(file_type="cctv"):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    if file_type == "excel":
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
    else:
        file_path = filedialog.askopenfilename(
            title="Select CCTV File",
            filetypes=[
                ("Image files", "*.jpeg *.jpg *.png *.heic"),
                ("Video files", "*.mov *.mp4 *.avi")
            ]
        )
    root.destroy()
    return file_path

# Folder selection function (cross-platform)
def select_output_folder():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory(title="Select Output Folder")
    root.destroy()
    return folder_path

st.title("Corinthian")

# Initialize session state for file selections
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'excel_selected' not in st.session_state:
    st.session_state.excel_selected = None
if 'output_folder' not in st.session_state:
    st.session_state.output_folder = str(Path.home() / "Corinthian_Results")

# Sidebar inputs
caseid = st.text_input("CaseID")
iname = st.text_input("Investigator's Name")

# Check if both required fields are filled
required_fields_filled = caseid and iname

if not required_fields_filled:
    st.warning("Please enter both CaseID and Investigator's Name to proceed")
    st.stop()

st.success("CaseID and Investigator Name added. You can now proceed.")

# File selection controls
ALLOWED_EXTENSIONS = {'.jpeg', '.jpg', '.png', '.mov', '.mp4', '.avi', '.heic'}
def is_allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

# File selection button
if st.button("Browse for CCTV File"):
    if sys.platform == "darwin":
        selected_cctv = get_file_mac("cctv")
    else:
        selected_cctv = get_file_others("cctv")
    if selected_cctv:
        if not is_allowed_file(selected_cctv):
            st.error("Invalid file type selected. Please select an image or video file (jpeg, jpg, png, mov, mp4, avi, heic).")
        else:
            st.session_state.selected_file = selected_cctv
            st.success(f"Selected: {st.session_state.selected_file}")
    else:
        st.info("No file selected.")

# Excel file selection
if st.button("Browse for Excel File"):
    if sys.platform == "darwin":
        selected_excel = get_file_mac("excel")
    else:
        selected_excel = get_file_others("excel")
    if selected_excel:
        if not selected_excel.lower().endswith(('.xlsx', '.xls')):
            st.error("Please select an Excel file (.xlsx or .xls)")
        else:
            st.session_state.excel_selected = selected_excel
            st.success(f"Selected: {st.session_state.excel_selected}")
    else:
        st.info("No file selected.")

# Output folder selection
if st.button("Select Output Folder"):
    selected_folder = select_output_folder()
    if selected_folder:
        st.session_state.output_folder = selected_folder
        st.success(f"Output Folder: {st.session_state.output_folder}")
    else:
        st.info("No folder selected. Using default.")

# ALWAYS display currently selected files BEFORE any st.stop paths
if st.session_state.selected_file:
    st.info(f"CCTV File: {st.session_state.selected_file}")
if st.session_state.excel_selected:
    st.info(f"Excel File: {st.session_state.excel_selected}")
st.info(f"Output Folder: {st.session_state.output_folder}")

# Detection options
st.subheader("Detection Options")
default_weights = os.path.join(current_dir, "..", "src", "yolov8n.pt")
yolo_weights = st.text_input("YOLO weights path", value=os.path.abspath(default_weights))
conf = st.slider("YOLO confidence", min_value=0.1, max_value=0.9, value=0.5, step=0.05)

# Performance controls
frame_skip = st.slider("Frame skip (process every Nth frame)", min_value=1, max_value=5, value=2, step=1)  # 1 = every frame
imgsz = st.selectbox("YOLO input size (imgsz)", options=[480, 640, 720], index=1)
tolerance = st.slider("Face match tolerance", min_value=0.3, max_value=0.8, value=0.5, step=0.05)

# Process button
if st.button("Process File"):
    # Validate inputs
    if not st.session_state.selected_file:
        st.error("Please select a CCTV file.")
        st.stop()

    if not st.session_state.excel_selected:
        st.error("Please select the Excel file with references.")
        st.stop()

    # Use the session state variables
    output_folder = st.session_state.output_folder
    selected_file = st.session_state.selected_file
    excel_selected = st.session_state.excel_selected

    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            st.error(f"Cannot create output folder: {e}")
            st.stop()

    # Verify selected file exists
    if not os.path.exists(selected_file):
        st.error(f"Selected file missing: {selected_file}")
        st.stop()

    # Parse Excel references (supports either 'photo' or 'Photos/PhotoN' schema)
    parse_ok = True
    references = {}
    try:
        df = pd.read_excel(excel_selected, engine="openpyxl")
        # Prefer a strict schema if provided: Name + photo (single file path per row)
        if 'Name' in df.columns and 'photo' in df.columns:
            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip()
                photo_path = str(row.get('photo', '')).strip()
                if name and photo_path and photo_path.lower() != 'nan' and os.path.exists(photo_path):
                    references.setdefault(name, []).append(photo_path)
        # Otherwise, allow Photos (comma-separated) or PhotoN columns
        else:
            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip()
                if not name:
                    continue
                img_paths = []
                if 'Photos' in df.columns and pd.notnull(row.get('Photos')):
                    for p in str(row['Photos']).split(','):
                        pth = p.strip()
                        if pth and os.path.exists(pth):
                            img_paths.append(pth)
                for col in df.columns:
                    if col.startswith('Photo') and pd.notnull(row.get(col)):
                        pth = str(row[col]).strip()
                        if pth and pth.lower() != 'nan' and os.path.exists(pth):
                            img_paths.append(pth)
                if img_paths:
                    references[name] = img_paths
        if not references:
            st.warning("No valid reference images found in Excel. Please verify absolute file paths.")
    except Exception as e:
        parse_ok = False
        st.error(f"Failed to parse Excel: {e}")

    if not parse_ok:
        st.stop()
    else:
        st.success(f"Loaded references for {len(references)} people.")

    # Log evidence metadata
    evidence_metadata = {}
    try:
        sha256, metadata = log_evidence_from_path(selected_file, camera_id="CCTV-1")
        evidence_metadata = metadata
        st.json(metadata)
    except Exception as e:
        st.warning(f"Metadata logging failed: {e}")

    try:
        from src.ai_detection import run_ai_detection
    except ImportError:
        st.error("Could not import ai_detection. Ensure ai_detection.py is alongside app.py and defines run_ai_detection.")
        st.stop()

    # Run AI Person Detection
    with st.spinner("Running AI person detection..."):
        try:
            person_result = run_ai_detection(
                input_video=selected_file,
                output_dir=output_folder,
                references=references,
                yolo_weights=yolo_weights,
                conf=conf,
                frame_skip=frame_skip,
                imgsz=imgsz,
                tolerance=tolerance,
            )
            st.success("Person detection completed successfully!")
        except Exception as e:
            st.error(f"Person detection failed: {e}")
            person_result = {"detections": {}, "output_video": None, "report_path": None}

    try:
        from src.tdetection import run_tamper_detection
    except ImportError:
        st.error("Could not import tdetection. Ensure tdetection.py is alongside app.py.")
        st.stop()

    # Run Tamper Detection
    with st.spinner("Running tamper detection..."):
        try:
            t_video, t_csv, tamper_times = run_tamper_detection(selected_file, output_folder)
            st.success("Tamper detection completed successfully!")
        except Exception as e:
            st.error(f"Tamper detection failed: {e}")
            t_video, t_csv, tamper_times = None, None, []

    # Generate comprehensive PDF report instead of text report
    pdf_report_path = os.path.join(output_folder, "forensic_analysis_report.pdf")
    
    # Prepare data for the PDF report
    report_data = {
        "report_id": str(uuid.uuid4())[:8].upper(),
        "case_id": caseid,
        "investigator": iname,
        "generating_system_version": "Corinthian v1.0",
        "evidence_list": [
            {
                "filename": os.path.basename(selected_file),
                "sha256": evidence_metadata.get('sha256', 'N/A'),
                "ingest_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "camera_id": "CCTV-1",
                "duration": evidence_metadata.get('duration', 'N/A'),
                "metadata": evidence_metadata
            }
        ],
        "findings": [],
        "forensics": {
            "metadata_summary": evidence_metadata,
            "tamper_flags": [{"time": str(timedelta(seconds=t)), "explanation": "Potential tampering detected"} for t in tamper_times] if tamper_times else [],
            "deepfake_score": 0.15  # Placeholder - would need actual deepfake detection
        },
        "signatures": {
            "report_sha256": "N/A",  # Will be calculated by generate_report
            "signature": "N/A",  # Placeholder for digital signature
            "signing_cert_subject": "N/A",
            "signing_cert_pubkey_fingerprint": "N/A"
        },
        "access_log_summary": {
            "total_accesses": 1,
            "first_access": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_access": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "users": [iname]
        }
    }
    
    # Convert person detection results to findings format
    for name, timestamps in person_result.get("detections", {}).items():
        for ts in set(timestamps):
            report_data["findings"].append({
                "time_window": f"{ts} - {ts}",  # Simplified - would need actual time windows
                "track_id": "N/A",  # Would need to extract from detection results
                "object_type": "Person",
                "representative_frame_path": "N/A",  # Would need to extract frames
                "bounding_box": [0, 0, 0, 0],  # Placeholder
                "matched_offender_id": name.split()[0] if ' ' in name else name,
                "matched_offender_name": name,
                "similarity_score": 0.85,  # Placeholder - would need actual similarity scoring
                "verification_status": "unverified"  # Would need verification system
            })
    
    # Generate the PDF report
    with st.spinner("Generating comprehensive PDF report..."):
        try:
            generate_report(report_data, pdf_report_path)
            st.success(f"PDF report generated: {pdf_report_path}")
        except Exception as e:
            st.error(f"Failed to generate PDF report: {e}")
            pdf_report_path = None

    # Display outputs and info
    st.caption(f"Used settings: frame_skip={frame_skip}, imgsz={imgsz}, tolerance={tolerance}, conf={conf}")
    st.subheader("Analysis Results")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Person Detection")
        if person_result.get("output_video") and os.path.exists(person_result["output_video"]):
            st.info(f"Annotated video: {person_result['output_video']}")
    with col2:
        st.write("Tamper Detection")
        if t_video and os.path.exists(t_video):
            st.info(f"Tamper video: {t_video}")
        if t_csv and os.path.exists(t_csv):
            st.info(f"Tamper CSV: {t_csv}")
    
    # Only show the PDF report (removed text reports)
    if pdf_report_path and os.path.exists(pdf_report_path):
        st.info(f"Comprehensive PDF Report: {pdf_report_path}")
        
        # Provide download button for the PDF
        with open(pdf_report_path, "rb") as f:
            pdf_data = f.read()
        st.download_button(
            label="Download PDF Report",
            data=pdf_data,
            file_name="forensic_analysis_report.pdf",
            mime="application/pdf"
        )