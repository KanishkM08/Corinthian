import hashlib
import os
import datetime
import csv
import cv2
import json
import sys
import tempfile
from io import BytesIO

# Add the dashboard directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
dashboard_dir = os.path.join(current_dir, '..')
sys.path.insert(0, os.path.abspath(dashboard_dir))

from dashboard.app import file

# # Add the dashboard directory to Python path
# current_dir = os.path.dirname(os.path.abspath(__file__))
# dashboard_dir = os.path.join(current_dir, '..')
# sys.path.insert(0, os.path.abspath(dashboard_dir))

# from src.metadata import log_metadata_from_streamlit

CSV_FILE = "audit_log.csv"

# sha256 
def compute_sha256_from_bytes(file_bytes):
    sha256 = hashlib.sha256()
    sha256.update(file_bytes)
    return sha256.hexdigest()

# Extract video metadata from file bytes
def extract_video_metadata_from_bytes(file_bytes, original_filename):
    metadata = {}
    
    # Create a temporary file to work with OpenCV
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(original_filename)[1], delete=False) as temp_file:
        temp_file.write(file_bytes)
        temp_file_path = temp_file.name
    
    try:
        # Use the temporary file path with OpenCV
        cap = cv2.VideoCapture(temp_file_path)

        # Frame count and FPS
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        metadata["frame_count"] = frame_count
        metadata["fps"] = fps if fps > 0 else None

        # Duration from OpenCV
        if fps > 0:
            duration_sec = frame_count / fps
            metadata["duration_sec"] = round(duration_sec, 3)
            # Human-readable format HH:MM:SS
            metadata["duration_hms"] = str(datetime.timedelta(seconds=int(duration_sec)))
        else:
            metadata["duration_sec"] = None
            metadata["duration_hms"] = None

        # Resolution
        metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

    except Exception as e:
        metadata["error"] = str(e)
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)

    # File-system-level info (current time for ingest)
    metadata["file_size_bytes"] = len(file_bytes)
    metadata["created_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metadata["modified_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return metadata

# Log evidence from Streamlit uploaded file object
def log_evidence_from_streamlit(uploaded_file, camera_id="unknown", action="ingest"):
    # Read the file bytes
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name
    sha256 = compute_sha256_from_bytes(file_bytes)
    metadata = extract_video_metadata_from_bytes(file_bytes, filename)
    ingest_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    row = [
        filename,
        sha256,
        ingest_time,
        camera_id,
        metadata.get("duration_sec"),
        json.dumps(metadata, ensure_ascii=False)
    ]

    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["filename", "sha256", "ingest_time", "camera_id", "duration_sec", "metadata_json"])
        writer.writerow(row)

    return sha256, metadata
 
def verify_file_from_bytes(file_bytes):
    """Return True if computed SHA256 exists in the CSV audit log from file bytes"""
    current_hash = compute_sha256_from_bytes(file_bytes)
    if not os.path.isfile(CSV_FILE):
        return False
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        stored_hashes = [row["sha256"] for row in reader if "sha256" in row]
    return current_hash in stored_hashes
