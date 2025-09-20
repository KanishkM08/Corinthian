import os
import sys
import streamlit as st
import pandas as pd
from pathlib import Path

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

st.title("Corinthian")

# Initialize session state for file selections
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'excel_selected' not in st.session_state:
    st.session_state.excel_selected = None

# Sidebar inputs
caseid = st.text_input("CaseID")
if caseid:
    st.success("CaseID added")
else:
    st.warning("CaseID is required to proceed")

iname = st.text_input("Investigator's Name")
if iname:
    st.success("Name saved")
else:
    st.warning("Investigator's name is required to proceed")

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

# ALWAYS display currently selected files BEFORE any st.stop paths
if st.session_state.selected_file:
    st.info(f"CCTV File: {st.session_state.selected_file}")
if st.session_state.excel_selected:
    st.info(f"Excel File: {st.session_state.excel_selected}")

output_folder = st.text_input("Output Folder Path", value=str(Path.home() / "Corinthian_Results"))

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
    if not caseid or not iname:
        st.error("CaseID and Investigator's Name are required.")
        st.stop()

    if not st.session_state.selected_file:
        st.error("Please select a CCTV file.")
        st.stop()

    if not st.session_state.excel_selected:
        st.error("Please select the Excel file with references.")
        st.stop()

    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            st.error(f"Cannot create output folder: {e}")
            st.stop()

    # Use the session state variables
    selected_file = st.session_state.selected_file
    excel_selected = st.session_state.excel_selected

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
    try:
        sha256, metadata = log_evidence_from_path(selected_file, camera_id="CCTV-1")
        st.json(metadata)
    except Exception as e:
        st.warning(f"Metadata logging failed: {e}")

    try:
        # run_ai_detection must be the pure function (no hardcoded paths)
        from ai_detection import run_ai_detection
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
        from tdetection import run_tamper_detection
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

    # Generate combined report
    combined_report = os.path.join(output_folder, "combined_report.txt")
    try:
        with open(combined_report, "w", encoding="utf-8") as rpt:
            rpt.write("CORINTHIAN DETECTION REPORT\n")
            rpt.write("===========================\n\n")
            rpt.write(f"Case ID: {caseid}\n")
            rpt.write(f"Investigator: {iname}\n")
            rpt.write(f"Input File: {os.path.basename(selected_file)}\n")
            rpt.write(f"Settings: frame_skip={frame_skip}, imgsz={imgsz}, tolerance={tolerance}, conf={conf}\n")
            rpt.write(f"Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Person Detection Results
            rpt.write("PERSON DETECTION RESULTS:\n")
            rpt.write("-" * 40 + "\n")
            person_detections = person_result.get("detections", {})
            if person_detections:
                for name, times in sorted(person_detections.items()):
                    rpt.write(f"\n{name}:\n")
                    if times:
                        unique_times = sorted(set(times))
                        rpt.write(f" Total detections: {len(unique_times)}\n")
                        rpt.write(" Timestamps:\n")
                        for ts in unique_times:
                            rpt.write(f" - {ts}\n")
                    else:
                        rpt.write(" - No detections\n")
            else:
                rpt.write("No person detections found.\n")

            # Tamper Detection Results
            rpt.write("\n\nTAMPER DETECTION RESULTS:\n")
            rpt.write("-" * 40 + "\n")
            if tamper_times:
                rpt.write(f"Total tampering events detected: {len(tamper_times)}\n")
                rpt.write("Tampering timestamps:\n")
                for seconds in sorted(set(tamper_times)):
                    ts = str(pd.to_timedelta(seconds, unit='s')).split(".")[0]
                    rpt.write(f" - {ts}\n")
            else:
                rpt.write("No tampering events detected.\n")

            rpt.write("\n" + "=" * 50 + "\n")
            rpt.write("End of Report\n")
        st.success(f"Combined report saved at: {combined_report}")
    except Exception as e:
        st.error(f"Failed to write combined report: {e}")

    # Display outputs and info
    st.caption(f"Used settings: frame_skip={frame_skip}, imgsz={imgsz}, tolerance={tolerance}, conf={conf}")
    st.subheader("Analysis Results")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Person Detection")
        if person_result.get("output_video") and os.path.exists(person_result["output_video"]):
            st.info(f"Annotated video: {person_result['output_video']}")
        if person_result.get("report_path") and os.path.exists(person_result["report_path"]):
            st.info(f"Person report: {person_result['report_path']}")
    with col2:
        st.write("Tamper Detection")
        if t_video and os.path.exists(t_video):
            st.info(f"Tamper video: {t_video}")
        if t_csv and os.path.exists(t_csv):
            st.info(f"Tamper CSV: {t_csv}")
    if os.path.exists(combined_report):
        st.info(f"Combined report: {combined_report}")
