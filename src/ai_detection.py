import os
import cv2
import numpy as np
from typing import Dict, List, Any, Tuple
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

def _calculate_similarity_percentage(distance: float, tolerance: float = 0.5) -> float:
    """
    Convert face distance to similarity percentage.
    - distance = 0 → 100%
    - distance = tolerance → 70%
    - distance > tolerance → degrades toward 0%
    """
    if distance <= tolerance:
        # Linear interpolation between 100% at 0 and 70% at tolerance
        similarity = 70 + (1 - distance / tolerance) * 30
        return min(100, similarity)
    else:
        # For distances > tolerance, ramp from 70 → 0 over [tolerance, 2*tolerance]
        excess = distance - tolerance
        span = tolerance  # distance range over which we go 70 → 0
        similarity = max(0, 70 * (1 - excess / span))
        return similarity


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
    
    # Logs - Enhanced to store similarity scores
    detection_log = {n: [] for n in known_names}
    similarity_scores = {n: [] for n in known_names}  # New: store similarity scores
    
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
                    best_similarity = 0
                    
                    # Enhanced face matching with similarity calculation
                    for enc in encs:
                        for name, ref_encs in encoded_people.items():
                            # Calculate distances to all reference encodings for this person
                            distances = face_recognition.face_distance(ref_encs, enc)
                            min_distance = min(distances) if distances.size > 0 else float('inf')
                            
                            # Convert distance to similarity percentage
                            similarity = _calculate_similarity_percentage(min_distance, tolerance)
                            
                            # Use tolerance for matching, but also consider if this is the best match
                            if min_distance <= tolerance and similarity > best_similarity:
                                found = name
                                best_similarity = similarity
                    
                    if found:
                        label = f"{found} ({best_similarity:.1f}%)"
                        color = (0, 255, 0)
                        ts = _format_ts(frame_idx / max(fps, 1.0))
                        
                        # Store both timestamp and similarity score
                        detection_log.setdefault(found, []).append(ts)
                        similarity_scores.setdefault(found, []).append(best_similarity)
                    
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
    
    # Calculate average similarity scores for each person
    avg_similarities = {}
    for name in known_names:
        if similarity_scores.get(name):
            avg_similarities[name] = sum(similarity_scores[name]) / len(similarity_scores[name])
        else:
            avg_similarities[name] = 0.0
    
    return {
        "output_video": output_video if os.path.exists(output_video) else None,
        "report_path": report_path if (report_path and os.path.exists(report_path)) else None,
        "detections": {k: sorted(set(v)) for k, v in detection_log.items()},
        "similarity_scores": similarity_scores,  # New: detailed similarity scores
        "avg_similarities": avg_similarities,    # New: average similarity per person
        "frames": frame_idx,
        "fps": float(fps),
        "width": int(width),
        "height": int(height),
    }