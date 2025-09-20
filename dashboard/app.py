import os
import sys
import streamlit as st
from pathlib import Path

# Ensure "src" is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, os.path.abspath(src_dir))


# Add the dashboard directory to Python path
dashboard_dir = os.path.join(current_dir, '..')
sys.path.insert(0, os.path.abspath(dashboard_dir))

from src.metadata import log_evidence_from_path

st.title("Corinthian")

caseid = st.text_input("CaseID")
if caseid:
    st.success("CaseId added")
else:
    st.warning("CaseID is required to procees")

iname = st.text_input("Invertigator's Name")
if iname:
    st.success("Name saved")
else:
    st.warning("Inverstigator's name is required to proceed")

ALLOWED_EXTENSIONS = {'.jpeg', '.jpg', '.png', '.mov', '.mp4', '.avi', '.heic'}

def is_allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def get_file_mac():
    import subprocess
    script = '''
set chosenFile to POSIX path of (choose file with prompt "Select a CCTV file")
return chosenFile
'''
    proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if proc.returncode == 0:
        return proc.stdout.strip()
    return None

def get_file_others():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(
        title="Select CCTV File",
        filetypes=[
            ("Image files", "*.jpeg *.jpg *.png *.heic"),
            ("Video files", "*.mov *.mp4 *.avi"),
        ],
    )
    root.destroy()
    return file_path

def get_folder_mac():
    import subprocess
    script = '''
set chosenFolder to POSIX path of (choose folder with prompt "Select output folder for results")
return chosenFolder
'''
    proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    if proc.returncode == 0:
        return proc.stdout.strip()
    return None

def get_folder_others():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory(title="Select Output Folder for Results")
    root.destroy()
    return folder_path

if caseid and iname:
    # Initialize session state for file and folder paths
    if 'selected_file' not in st.session_state:
        st.session_state.selected_file = None
    if 'output_folder' not in st.session_state:
        st.session_state.output_folder = None

    # File selection button
    if st.button("Browse for File"):
        if sys.platform == "darwin":
            selected = get_file_mac()
        else:
            selected = get_file_others()
        if selected:
            if not is_allowed_file(selected):
                st.error("Invalid file type selected. Please select an image or video file (jpeg, jpg, png, mov, mp4, avi, heic).")
            else:
                st.session_state.selected_file = selected

    # Show selected file path persistently
    if st.session_state.selected_file:
        st.success(f"Selected file: {st.session_state.selected_file}")

    # Output folder selection button
    if st.button("Browse for Output Folder"):
        if sys.platform == "darwin":
            folder_selected = get_folder_mac()
        else:
            folder_selected = get_folder_others()
        if folder_selected:
            st.session_state.output_folder = folder_selected

    # Show selected output folder persistently
    if st.session_state.output_folder:
        st.success(f"Selected output folder: {st.session_state.output_folder}")

    # Extra options for AI detection
    st.subheader("Detection Options")
    default_weights = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "yolov8n.pt")
    yolo_weights = st.text_input("YOLO weights path", value=os.path.abspath(default_weights))
    conf = st.slider("Confidence threshold", min_value=0.1, max_value=0.9, value=0.5, step=0.05)

    # Example reference dictionary input (users can adjust in code or later via UI)
    # In practice, this can be read from a config file or UI inputs.
    references = {
        # "Person_A": [r"C:\path\to\person_a_1.jpg", r"C:\path\to\person_a_2.jpg"],
        # "Person_B": [r"C:\path\to\person_b.jpg"],
    }
    
    # Import AI person detection runner (to be implemented in ai_detection.py)
    # Expected signature:
    #   run_ai_detection(input_video: str, output_dir: str, references: dict, yolo_weights: str, conf: float) 
    #   -> dict with keys: {"output_video": str, "report_path": str, "detections": dict}
    from ai_detection import run_ai_detection  # make sure function exists in ai_detection.py
    # Process button - only enabled if both file and output folder are selected
    if st.session_state.selected_file and st.session_state.output_folder:
        if st.button("Process File"):
            try:
                # Log evidence metadata
                sha256, metadata = log_evidence_from_path(st.session_state.selected_file, camera_id="CCTV-1")
                st.json(metadata)

                with st.spinner("Running AI person detection..."):
                    result = run_ai_detection(
                        input_video=st.session_state.selected_file,
                        output_dir=st.session_state.output_folder,
                        references=references,
                        yolo_weights=yolo_weights,
                        conf=conf,
                    )

                # Expecting result dict with keys: output_video, report_path, detections
                output_video = result.get("output_video")
                report_path = result.get("report_path")
                detections = result.get("detections", {})

                if detections:
                    st.success("Person detection completed with matches found.")
                    # Flatten simple list of timestamps per person to messages
                    for name, times in detections.items():
                        if times:
                            st.info(f"{name} detected at: {', '.join(sorted(set(times)))}")
                        else:
                            st.info(f"{name}: no detections")
                else:
                    st.success("Person detection completed. No known references matched.")

                if output_video and os.path.exists(output_video):
                    st.info(f"Annotated video saved to: {output_video}")
                if report_path and os.path.exists(report_path):
                    st.info(f"Text report saved to: {report_path}")

            except Exception as e:
                st.error(f"Processing failed: {e}")

    # If process not possible, show corresponding warnings
    else:
        if not st.session_state.selected_file:
            st.warning("Please select a file to process.")
        if not st.session_state.output_folder:
            st.warning("Please select an output folder for results.")
