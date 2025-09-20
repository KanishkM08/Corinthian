import os
import cv2
import numpy as np
from typing import Dict, List, Any
from ultralytics import YOLO
import face_recognition
from datetime import timedelta

def _format_ts(seconds: float) -> str:
    return str(timedelta(seconds=seconds)).split(".")[0]

def _encode_references(references: Dict[str, List[str]]) -> Dict[str, List[np.ndarray]]:
    encoded = {}
    for name, paths in (references or {}).items():
        encs = []
        for p in paths:
            if not p or not os.path.exists(p):
                continue
            try:
                img = face_recognition.load_image_file(p)
                locs = face_recognition.face_locations(img, model="hog")
                feats = face_recognition.face_encodings(img, locs)
                if feats:
                    encs.append(feats[0])
            except Exception:
                continue
        if encs:
            encoded[name] = encs
    return encoded

def run_ai_detection(input_video: str,
                     output_dir: str,
                     references: Dict[str, List[str]] = None,
                     yolo_weights: str = None,
                     conf: float = 0.5,
                     frame_skip: int = 2,
                     imgsz: int = 640,
                     tolerance: float = 0.5) -> Dict[str, Any]:
    # Validate
    if not input_video or not os.path.exists(input_video):
        raise FileNotFoundError(f"Input video not found: {input_video}")
    if not yolo_weights or not os.path.exists(yolo_weights):
        raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
    os.makedirs(output_dir, exist_ok=True)

    # Outputs
    base = os.path.splitext(os.path.basename(input_video))[0]
    output_video = os.path.join(output_dir, f"{base}_person_annotated.mp4")
    report_path = os.path.join(output_dir, f"{base}_person_report.txt")

    # Load model
    model = YOLO(yolo_weights)
    try:
        model.fuse()
    except Exception:
        pass

    # Encode references
    encoded_people = _encode_references(references or {})
    known_names = list(encoded_people.keys())

    # Video IO
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {input_video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

    # Logs
    detection_log = {n: [] for n in known_names}
    frame_idx = 0
    ROI_MAX_W = 320

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            if frame_idx % max(1, int(frame_skip)) == 0:
                results = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    conf=float(conf),
                    iou=0.6,
                    imgsz=int(imgsz),
                    classes=[0],
                    verbose=False
                )
                boxes = results[0].boxes.xyxy.cpu().numpy() if results and results[0].boxes is not None else []
                ids = (results[0].boxes.id.cpu().numpy().astype(int)
                       if results and results[0].boxes is not None and results[0].boxes.id is not None
                       else np.full((len(boxes),), -1, dtype=int))

                for (x1f, y1f, x2f, y2f), tid in zip(boxes, ids):
                    x1, y1, x2, y2 = map(int, [x1f, y1f, x2f, y2f])
                    x1 = max(0, min(x1, width - 1))
                    x2 = max(0, min(x2, width - 1))
                    y1 = max(0, min(y1, height - 1))
                    y2 = max(0, min(y2, height - 1))
                    if x2 <= x1 or y2 <= y1:
                        continue

                    roi = frame[y1:y2, x1:x2]
                    if roi.size == 0:
                        continue

                    # Downscale ROI for faster HOG
                    h, w = roi.shape[:2]
                    if max(h, w) > ROI_MAX_W:
                        scale = ROI_MAX_W / float(max(h, w))
                        roi = cv2.resize(roi, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)

                    label = f"ID:{tid}" if tid != -1 else "Unknown"
                    color = (0, 0, 255)

                    try:
                        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(rgb, model="hog")
                        encs = face_recognition.face_encodings(rgb, locs)
                    except Exception:
                        encs = []

                    found = None
                    for enc in encs:
                        for name, ref_encs in encoded_people.items():
                            if True in face_recognition.compare_faces(ref_encs, enc, tolerance=float(tolerance)):
                                found = name
                                break
                        if found:
                            break

                    if found:
                        label = found
                        color = (0, 255, 0)
                        ts = _format_ts(frame_idx / max(fps, 1.0))
                        detection_log.setdefault(found, []).append(ts)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, max(0, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, lineType=cv2.LINE_AA)

            writer.write(frame)

    finally:
        cap.release()
        writer.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    # Report
    try:
        with open(report_path, "w", encoding="utf-8") as rpt:
            rpt.write("Person Detection Report\n")
            rpt.write("=======================\n\n")
            for name in sorted(detection_log.keys()):
                times = sorted(set(detection_log.get(name, [])))
                rpt.write(f"{name}:\n")
                if times:
                    for t in times:
                        rpt.write(f" - {t}\n")
                else:
                    rpt.write(" - No detections\n")
                rpt.write("\n")
    except Exception:
        report_path = None

    return {
        "output_video": output_video if os.path.exists(output_video) else None,
        "report_path": report_path if (report_path and os.path.exists(report_path)) else None,
        "detections": {k: sorted(set(v)) for k, v in detection_log.items()},
        "frames": frame_idx,
        "fps": float(fps),
        "width": int(width),
        "height": int(height),
    }
