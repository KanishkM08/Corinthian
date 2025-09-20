import hashlib
import os
import datetime
import csv
import cv2
import json

CSV_FILE = "audit_log.csv"

# sha256
def compute_sha256_from_file(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

# Extract video metadata from file path
def extract_video_metadata_from_path(file_path):
    metadata = {}
    try:
        cap = cv2.VideoCapture(file_path)

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        metadata["frame_count"] = frame_count
        metadata["fps"] = fps if fps > 0 else None

        if fps > 0:
            duration_sec = frame_count / fps
            metadata["duration_sec"] = round(duration_sec, 3)
            metadata["duration_hms"] = str(datetime.timedelta(seconds=int(duration_sec)))
        else:
            metadata["duration_sec"] = None
            metadata["duration_hms"] = None

        metadata["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        metadata["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

    except Exception as e:
        metadata["error"] = str(e)

    # File-system info
    stat_info = os.stat(file_path)
    metadata["file_size_bytes"] = stat_info.st_size
    metadata["created_time"] = datetime.datetime.fromtimestamp(stat_info.st_ctime, datetime.timezone.utc).isoformat()
    metadata["modified_time"] = datetime.datetime.fromtimestamp(stat_info.st_mtime, datetime.timezone.utc).isoformat()

    return metadata

# Log evidence from file path
def log_evidence_from_path(file_path, camera_id="unknown", action="ingest"):
    filename = os.path.basename(file_path)
    sha256 = compute_sha256_from_file(file_path)
    metadata = extract_video_metadata_from_path(file_path)
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

# Verify by path
def verify_file_from_path(file_path):
    current_hash = compute_sha256_from_file(file_path)
    if not os.path.isfile(CSV_FILE):
        return False
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        stored_hashes = [row["sha256"] for row in reader if "sha256" in row]
    return current_hash in stored_hashes
