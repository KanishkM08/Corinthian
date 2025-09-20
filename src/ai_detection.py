import os
import cv2
from datetime import timedelta
from typing import Dict, List, Any, Tuple

import numpy as np
from ultralytics import YOLO
import face_recognition


def _encode_references(references: Dict[str, List[str]]) -> Dict[str, List[np.ndarray]]:
    """
    Load and encode all reference images for each person.
    """
    if not isinstance(references, dict) or not references:
        return {}

    encoded_people: Dict[str, List[np.ndarray]] = {}
    for name, images in references.items():
        enc_list: List[np.ndarray] = []
        for img_path in images:
            if not img_path or not os.path.exists(img_path):
                # Skip missing reference images
                continue
            try:
                img = face_recognition.load_image_file(img_path)
                locs = face_recognition.face_locations(img, model="hog")
                encs = face_recognition.face_encodings(img, locs)
                if encs:
                    enc_list.append(encs[0])
            except Exception:
                # Ignore problematic reference images
                continue
        if enc_list:
            encoded_people[name] = enc_list
    return encoded_people


def _safe_video_writer(output_path: str, fps: float, size: Tuple[int, int]) -> cv2.VideoWriter:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(output_path, fourcc, max(fps, 1.0), size)


def _format_ts(seconds: float) -> str:
    return str(timedelta(seconds=seconds)).split(".")[0]


def run_ai_detection(
    input_video: str,
    output_dir: str,
    references: Dict[str, List[str]] = None,
    yolo_weights: str = None,
    conf: float = 0.5,
) -> Dict[str, Any]:
    """
    Run YOLOv8 person detection + ByteTrack tracking, crop faces within person boxes,
    match against provided reference encodings, draw annotations, and write:
      - annotated output video
      - text report of detection timestamps

    Parameters
    - input_video: path to input video (or single image; video strongly recommended)
    - output_dir: directory where outputs will be written
    - references: dict { "Name": [list_of_image_paths] } for face matching
    - yolo_weights: path to YOLOv8 weights (e.g., yolov8n.pt)
    - conf: detection confidence threshold (0.1 to 0.9 typical)

    Returns dict:
    {
        "output_video": str or None,
        "report_path": str or None,
        "detections": Dict[str, List[str]],  # person -> list of HH:MM:SS timestamps
        "frames": int,
        "fps": float,
        "width": int,
        "height": int
    }
    """
    # Validate inputs
    if not input_video or not os.path.exists(input_video):
        raise FileNotFoundError(f"Input not found: {input_video}")
    if not output_dir:
        raise ValueError("Output directory not provided")

    os.makedirs(output_dir, exist_ok=True)

    # Build output paths
    base = os.path.splitext(os.path.basename(input_video))[0]
    output_video = os.path.join(output_dir, f"{base}_annotated.mp4")
    report_path = os.path.join(output_dir, f"{base}_report.txt")

    # Load model
    if not yolo_weights or not os.path.exists(yolo_weights):
        raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
    model = YOLO(yolo_weights)

    # Encode references
    references = references or {}
    encoded_people = _encode_references(references)
    known_names = set(encoded_people.keys())

    # Video I/O
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {input_video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    writer = _safe_video_writer(output_video, fps, (width, height))

    # Detection log: {name: [timestamps]}
    detection_log: Dict[str, List[str]] = {name: [] for name in known_names}
    frame_index = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_index += 1

            # Person detection + tracking
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=float(conf),
                classes=[0],  # person class
                verbose=False,
            )

            # If no detections, just write frame
            if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                writer.write(frame)
                continue

            r0 = results[0]
            boxes_xyxy = r0.boxes.xyxy.cpu().numpy()
            ids = (
                r0.boxes.id.cpu().numpy().astype(int)
                if (getattr(r0.boxes, "id", None) is not None)
                else np.full((len(boxes_xyxy),), -1, dtype=int)
            )

            for (x1f, y1f, x2f, y2f), track_id in zip(boxes_xyxy, ids):
                x1, y1, x2, y2 = map(int, [x1f, y1f, x2f, y2f])
                x1 = max(0, min(x1, frame.shape[1] - 1))
                x2 = max(0, min(x2, frame.shape[1] - 1))
                y1 = max(0, min(y1, frame.shape[0] - 1))
                y2 = max(0, min(y2, frame.shape[0] - 1))
                if x2 <= x1 or y2 <= y1:
                    continue

                person_roi = frame[y1:y2, x1:x2]
                label = f"Person {track_id}" if track_id != -1 else "Unknown"
                color = (255, 0, 0)  # default blue-ish for unknowns

                # Face recognition within the person ROI
                try:
                    if person_roi.size > 0 and encoded_people:
                        rgb = cv2.cvtColor(person_roi, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(rgb, model="hog")
                        encs = face_recognition.face_encodings(rgb, locs)

                        found_name = None
                        for enc in encs:
                            for name, ref_encs in encoded_people.items():
                                matches = face_recognition.compare_faces(ref_encs, enc, tolerance=0.5)
                                if True in matches:
                                    found_name = name
                                    break
                            if found_name:
                                break

                        if found_name:
                            label = found_name
                            color = (0, 255, 0)
                            # Timestamp logging
                            seconds = frame_index / max(fps, 1.0)
                            ts = _format_ts(seconds)
                            detection_log.setdefault(found_name, []).append(ts)
                except Exception:
                    # Fail-safe: keep default label if face pipeline errors
                    pass

                # Draw annotation
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame,
                    label,
                    (x1, max(0, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    color,
                    2,
                    lineType=cv2.LINE_AA,
                )

            writer.write(frame)
    finally:
        cap.release()
        writer.release()
        # No GUI in Streamlit context
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    # Generate report (dedup + sort)
    try:
        with open(report_path, "w", encoding="utf-8") as rpt:
            rpt.write("Detection Report\n")
            rpt.write("================\n\n")
            for name in sorted(detection_log.keys()):
                times = detection_log.get(name, [])
                rpt.write(f"{name}:\n")
                if times:
                    unique_ts = sorted(set(times))
                    for ts in unique_ts:
                        rpt.write(f" - {ts}\n")
                else:
                    rpt.write(" No detections\n")
                rpt.write("\n")
    except Exception:
        # If report writing fails, still return other outputs
        report_path = None

    return {
        "output_video": output_video if os.path.exists(output_video) else None,
        "report_path": report_path if (report_path and os.path.exists(report_path)) else None,
        "detections": {k: sorted(set(v)) for k, v in detection_log.items()},
        "frames": frame_index,
        "fps": float(fps),
        "width": int(width),
        "height": int(height),
    }
