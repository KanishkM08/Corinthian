import cv2
import numpy as np
import csv
import os
from pathlib import Path

# === Thresholds ===
LAP_VAR_THRESHOLD = 5
BRIGHTNESS_DROP = 0.05
PERSISTENCE_SECONDS = 0.6
SAMPLE_FPS = 4

def variance_of_laplacian(image):
    return cv2.Laplacian(image, cv2.CV_64F).var()

def brightness_mean(image):
    return np.mean(image)

def run_tamper_detection(file_path, output_dir=None):
    """Process video for tampering, save annotated video + CSV, return outputs + timestamps."""
    if output_dir is None:
        output_dir = str(Path.home() / "Desktop")

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise RuntimeError("Error: Cannot open video")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(int(fps / SAMPLE_FPS), 1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    output_video = os.path.join(output_dir, "tamper_annotated.mp4")
    output_csv = os.path.join(output_dir, "tamper_log.csv")

    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

    persistence_frames = max(1, int(PERSISTENCE_SECONDS * SAMPLE_FPS))

    tamper_events = []

    with open(output_csv, "w", newline="") as log_file:
        csv_writer = csv.writer(log_file)
        csv_writer.writerow(["frame", "timestamp", "event", "score", "note"])

        frame_idx = 0
        cover_counter = 0
        baseline_brightness = None
        cover_active = False

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval != 0:
                frame_idx += 1
                continue

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

            event = "NONE"
            note = f"lap_var={lap_var:.2f}, bright_ratio={brightness_ratio:.2f}"

            if cover_counter >= persistence_frames and not cover_active:
                cover_active = True
                event = "COVER"
                note = "Tampering detected"
                ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                tamper_events.append(ts)

            elif cover_active and cover_counter == 0:
                cover_active = False
                event = "UNCOVER"
                note = "Tampering ended"

            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            csv_writer.writerow([frame_idx, f"{ts:.2f}", event, f"{lap_var:.2f}", note])

            overlay = frame.copy()
            if cover_active:
                cv2.rectangle(overlay, (0, 0), (width, 40), (0, 0, 0), -1)
                cv2.putText(overlay, "TAMPERING DETECTED", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            out.write(overlay)

            frame_idx += 1

    cap.release()
    out.release()

    return output_video, output_csv, tamper_events
