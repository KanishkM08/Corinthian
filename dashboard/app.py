import os
import sys
import streamlit as st
import pandas as pd
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import platform
from datetime import datetime

system_version = f"{platform.system()} {platform.release()}"

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

# Import car detection

from src.car_detection import run_car_detection


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
    import platform
    import subprocess

    system = platform.system()
    if system == "Darwin":  # macOS
        script = '''
        set chosenFolder to POSIX path of (choose folder with prompt "Select Output Folder")
        return chosenFolder
        '''
        proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if proc.returncode == 0:
            return proc.stdout.strip()
        return None
    else:  # Windows/Linux
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

# ALWAYS display currently selected files BEFORE any st.stop() paths
st.subheader("Detection Options")
default_weights = os.path.join(current_dir, "..", "src", "yolov8n.pt")
yolo_weights = st.text_input("YOLO weights path:", value=os.path.abspath(default_weights))
conf = st.slider("YOLO confidence", min_value=0.1, max_value=0.9, value=0.5, step=0.05)

# Detection options
frame_skip = st.slider("Frame skip (process every Nth frame)", min_value=1, max_value=5, value=2, step=1)  # 1 = every frame
imgsz = st.selectbox("YOLO input size (imgsz)", options=[480, 640, 720], index=1)
tolerance = st.slider("Face match tolerance", min_value=0.3, max_value=0.8, value=0.5, step=0.05)

# Info message about car detection
st.info("Car detection will run automatically alongside person detection.")

# Performance controls
if st.button("Process File"):
    # Process button
    if not st.session_state.selected_file:
        st.error("Please select a CCTV file.")
        st.stop()
    
    if not st.session_state.excel_selected:
        st.error("Please select the Excel file with references.")
        st.stop()
    
    # Validate inputs
    output_folder = st.session_state.output_folder
    selected_file = st.session_state.selected_file
    excel_selected = st.session_state.excel_selected
    
    if not os.path.exists(output_folder):
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            st.error(f"Cannot create output folder: {e}")
            st.stop()
    
    # Use the session state variables
    if not os.path.exists(selected_file):
        st.error(f"Selected file missing: {selected_file}")
        st.stop()
    
    # Verify selected file exists
    image_dir = "db"  # Directory where reference images are stored
    parse_ok = True
    references = {}
    
    try:
        df = pd.read_excel(excel_selected, engine='openpyxl')
        
        # Ensure required columns exist
        if "ID" in df.columns and "Name" in df.columns:
            for _, row in df.iterrows():
                person_id = str(row.get("ID", "")).strip()
                name = str(row.get("Name", "")).strip()
                
                if not person_id or not name:
                    continue
                
                # Try to find image file in db directory
                img_paths = []
                for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
                    candidate = os.path.join(image_dir, person_id + ext)
                    if os.path.exists(candidate):
                        img_paths.append(candidate)
                
                if img_paths:
                    references[name] = img_paths
        
        if not references:
            st.warning("No valid reference images found in db/. Make sure IDs in Excel match filenames.")
    
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
    
    # Import the updated ai_detection module
    try:
        from src.ai_detection import run_ai_detection
    except ImportError:
        st.error("Could not import ai_detection. Ensure ai_detection.py is updated and available.")
        st.stop()
    
    # Run both AI Person Detection and Car Detection
    person_result = None
    car_result = None
    
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
            person_result = {
                "detections": {},
                "avg_similarities": {},
                "output_video": None,
                "report_path": None,
                "similarity_scores": {}
            }
    
    # Run Car Detection automatically
    with st.spinner("Running car detection..."):
        try:
            car_result = run_car_detection(
                input_video=selected_file,
                output_dir=output_folder,
                yolo_weights=yolo_weights,
                conf=conf,
                frame_skip=frame_skip,
                imgsz=imgsz,
            )
            st.success("Car detection completed successfully!")
        except Exception as e:
            st.error(f"Car detection failed: {e}")
            car_result = {
                "total_vehicles": 0,
                "vehicles_with_plates": 0,
                "total_plates": 0,
                "vehicle_detections": {},
                "plate_detections": {},
                "output_video": None
            }
    
    # Run Tamper Detection
    try:
        from src.tdetection import run_tamper_detection
    except ImportError:
        st.error("Could not import tdetection. Ensure tdetection.py is alongside app.py.")
        st.stop()
    
    with st.spinner("Running tamper detection..."):
        try:
            tvideo, tcsv, tamper_times = run_tamper_detection(selected_file, output_folder)
            st.success("Tamper detection completed successfully!")
        except Exception as e:
            st.error(f"Tamper detection failed: {e}")
            tvideo, tcsv, tamper_times = None, None, []
    
    # Generate comprehensive PDF report instead of text report
    pdf_report_path = os.path.join(output_folder, "forensic_analysis_report.pdf")
    
    # Prepare data for the PDF report
    report_data = {
        "report_id": str(uuid.uuid4()).upper(),
        "case_id": caseid,
        "investigator": iname,
        "generating_system_version": system_version,
        "evidence_list": [{
            "filename": os.path.basename(selected_file),
            "sha256": sha256 if 'sha256' in locals() else "N/A",
            "ingest_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": "CCTV-1",
        }],
        "findings": [],
        "forensics": {
            "metadata_summary": evidence_metadata,
            "tamper_flags": [{"time": str(timedelta(seconds=t)), "explanation": "Potential tampering detected"} 
                           for t in tamper_times] if tamper_times else [],
            "deepfake_score": 0.15  # Placeholder - would need actual deepfake detection
        },
        "signatures": {},
        "access_log_summary": {
            "total_accesses": 1,
            "first_access": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_access": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "users": [iname]
        },
        "car_detection": {
            "total_vehicles": car_result["total_vehicles"],
            "vehicles_with_plates": car_result["vehicles_with_plates"],
            "total_plates": car_result["total_plates"],
            "vehicle_details": []
        }
    }
    
    # Convert person detection results to findings format using actual similarity scores
    from collections import defaultdict
    scores_by_ts = defaultdict(list)
    for name, timestamps in person_result.get("detections", {}).items():
        sims = person_result.get("similarity_scores", {}).get(name, [])
        for ts, sim in zip(timestamps, sims):
            scores_by_ts[(name, ts)].append(sim)
    
    for (name, ts), sim_list in scores_by_ts.items():
        max_sim = max(sim_list) if sim_list else 0
        report_data["findings"].append({
            "time_window": ts,
            "track_id": "N/A",
            "object_type": "Person",
            "representative_frame_path": "N/A",
            "bounding_box": [0, 0, 0, 0],
            "matched_offender_id": name,
            "matched_offender_name": name,
            "similarity_score": max_sim / 100.0,
            "verification_status": "unverified"
        })
    
    # Add car detection results to findings
    for track_id, vehicle_info in car_result.get("vehicle_detections", {}).items():
        vehicle_type = vehicle_info.get("type", "unknown")
        detection_times = vehicle_info.get("detections", [])
        plates = vehicle_info.get("plates", [])
        
        # Create a finding for each unique detection time
        for detection_time in set(detection_times):
            plate_info = f"Plates: {', '.join(plates)}" if plates else "No plates detected"
            
            report_data["findings"].append({
                "time_window": detection_time,
                "track_id": str(track_id),
                "object_type": vehicle_type,
                "representative_frame_path": "N/A",
                "bounding_box": [0, 0, 0, 0],
                "matched_offender_id": f"Vehicle_{track_id}",
                "matched_offender_name": f"{vehicle_type} ID:{track_id} ({plate_info})",
                "similarity_score": 1.0 if plates else 0.5,  # Higher score if plates found
                "verification_status": "verified" if plates else "unverified"
            })
    
    # Add car detection results to separate car_detection section for detailed reporting
    report_data["car_detection"] = {
        "total_vehicles": car_result["total_vehicles"],
        "vehicles_with_plates": car_result["vehicles_with_plates"],
        "total_plates": car_result["total_plates"],
        "vehicle_details": []
    }
    
    for track_id, vehicle_info in car_result.get("vehicle_detections", {}).items():
        report_data["car_detection"]["vehicle_details"].append({
            "track_id": track_id,
            "vehicle_type": vehicle_info.get("type", "unknown"),
            "detection_count": len(vehicle_info.get("detections", [])),
            "plates": vehicle_info.get("plates", [])
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
        st.write("**Person Detection**")
        if person_result.get("output_video") and os.path.exists(person_result["output_video"]):
            st.info(f"Annotated video: {person_result['output_video']}")
        
        # Display detection results with similarity scores
        if person_result.get("detections"):
            st.write("**Detected Persons:**")
            for name, timestamps in person_result["detections"].items():
                st.write(f"- {name}: {len(timestamps)} detections")

    with col2:
        st.write("**Car Detection**")
        st.metric("Total Vehicles", car_result["total_vehicles"])
        st.metric("Vehicles with Plates", car_result["vehicles_with_plates"])
        st.metric("Total Plates Found", car_result["total_plates"])
        
        if car_result.get("output_video") and os.path.exists(car_result["output_video"]):
            st.info(f"Annotated car video: {car_result['output_video']}")
    
    st.write("**Tamper Detection**")
    if tvideo and os.path.exists(tvideo):
        st.info(f"Tamper video: {tvideo}")
    if tcsv and os.path.exists(tcsv):
        st.info(f"Tamper CSV: {tcsv}")
    
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