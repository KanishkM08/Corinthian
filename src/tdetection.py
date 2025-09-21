import cv2
import numpy as np
import csv
import os
from pathlib import Path
from datetime import timedelta

# === Thresholds ===
LAP_VAR_THRESHOLD = 5
BRIGHTNESS_DROP = 0.05
PERSISTENCE_SECONDS = 0.6
SAMPLE_FPS = 4

def variance_of_laplacian(image):
    """Calculate the variance of the Laplacian to measure image blurriness."""
    return cv2.Laplacian(image, cv2.CV_64F).var()

def brightness_mean(image):
    """Calculate the mean brightness of an image."""
    return np.mean(image)

def format_timestamp(seconds):
    """Format seconds into HH:MM:SS format."""
    return str(timedelta(seconds=seconds)).split(".")[0]

def run_tamper_detection(file_path, output_dir=None):
    """
    Process video for tampering detection, save annotated video + CSV, return outputs + timestamps.
    
    Args:
        file_path: Path to input video file
        output_dir: Directory to save outputs (defaults to Desktop)
    
    Returns:
        tuple: (output_video_path, output_csv_path, tamper_event_timestamps)
    """
    if output_dir is None:
        output_dir = str(Path.home() / "Desktop")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Open video
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise RuntimeError(f"Error: Cannot open video {file_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(int(fps / SAMPLE_FPS), 1)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Setup output files
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_video = os.path.join(output_dir, f"{base_name}_tamper_annotated.mp4")
    output_csv = os.path.join(output_dir, f"{base_name}_tamper_log.csv")
    
    # Video writer
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    
    # Detection variables
    persistence_frames = max(1, int(PERSISTENCE_SECONDS * SAMPLE_FPS))
    tamper_events = []
    
    frame_idx = 0
    cover_counter = 0
    baseline_brightness = None
    cover_active = False
    
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                lap_var = variance_of_laplacian(gray)
                bright = brightness_mean(gray)
                
                if baseline_brightness is None:
                    baseline_brightness = bright
                
                brightness_ratio = bright / (baseline_brightness + 1e-6)
                
                if lap_var < LAP_VAR_THRESHOLD or brightness_ratio < BRIGHTNESS_DROP:
                    cover_counter += 1
                else:
                    cover_counter = 0
                
                if cover_counter >= persistence_frames and not cover_active:
                    cover_active = True
                    ts = frame_idx / fps
                    tamper_events.append(ts)
                
                elif cover_active and cover_counter == 0:
                    cover_active = False
                    ts = frame_idx / fps
                    tamper_events.append(ts)
            
            overlay = frame.copy()
            if cover_active:
                cv2.rectangle(overlay, (0, 0), (width, 50), (0, 0, 255), -1)
                cv2.putText(
                    overlay,
                    "TAMPERING DETECTED",
                    (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (255, 255, 255),
                    2,
                    lineType=cv2.LINE_AA,
                )
                ts_text = format_timestamp(frame_idx / fps)
                cv2.putText(
                    overlay,
                    f"Time: {ts_text}",
                    (width - 200, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                    lineType=cv2.LINE_AA,
                )
            
            out.write(overlay)
            frame_idx += 1
    
    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        cap.release()
        out.release()

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    
    return output_video, output_csv, tamper_events

