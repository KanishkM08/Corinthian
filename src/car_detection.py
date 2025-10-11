import cv2
import easyocr
import os
from ultralytics import YOLO
from typing import Dict, List, Any, Tuple
from datetime import timedelta

# === INITIALIZATION FUNCTIONS ===

def init_reader():
    """Initialize and return an EasyOCR reader (English only)."""
    return easyocr.Reader(['en'], gpu=False)

def init_detector(model_path='yolov8n.pt'):
    """Initialize and return a YOLOv8 detector for vehicle detection + tracking."""
    return YOLO(model_path)

# === DETECTION + TRACKING FUNCTIONS ===

def detect_and_track_vehicles(frame, detector, vehicle_classes, conf_thresh=0.5, iou_thresh=0.4):
    """
    Detect + track vehicles using YOLOv8 + BYTETrack.
    Returns list of detections: [(track_id, vehicle_type, (x1,y1,x2,y2))]
    """
    results = detector.track(frame, conf=conf_thresh, iou=iou_thresh,
                             persist=True, tracker="bytetrack.yaml")[0]
    detections = []
    if results.boxes.id is None:
        return detections

    for cls, conf, box, track_id in zip(results.boxes.cls,
                                        results.boxes.conf,
                                        results.boxes.xyxy,
                                        results.boxes.id):
        cls_id = int(cls)
        if cls_id in vehicle_classes and conf > conf_thresh:
            vehicle_type = vehicle_classes[cls_id]
            x1, y1, x2, y2 = map(int, box.tolist())
            detections.append((int(track_id), vehicle_type, (x1, y1, x2, y2)))
    return detections

def detect_and_recognize_plates(frame, reader):
    """Detect rectangular regions likely to be license plates and recognize text via EasyOCR."""
    plates = []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(blur, 30, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1000 or area > 50000:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.018 * peri, True)
        if len(approx) != 4:
            continue

        x, y, w, h = cv2.boundingRect(approx)
        ar = w / float(h)
        if ar < 2.0 or ar > 5.0:
            continue

        plate_img = frame[y:y+h, x:x+w]
        results = reader.readtext(
            plate_img,
            detail=0,
            allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        )
        for text in results:
            cleaned = ''.join(c for c in text if c.isalnum()).upper()
            if len(cleaned) in (8, 9, 10):
                plates.append((cleaned, (x, y, w, h)))
    return plates

def _format_ts(seconds: float) -> str:
    return str(timedelta(seconds=seconds)).split(".")[0]

def run_car_detection(
    input_video: str,
    output_dir: str,
    yolo_weights: str = None,
    conf: float = 0.5,
    frame_skip: int = 2,
    imgsz: int = 640
) -> Dict[str, Any]:
    """
    Run car detection and license plate recognition on video.
    Returns detection results including vehicle counts and plate information.
    """
    # Validate
    if not input_video or not os.path.exists(input_video):
        raise FileNotFoundError(f"Input video not found: {input_video}")
    if not yolo_weights or not os.path.exists(yolo_weights):
        raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
        
    os.makedirs(output_dir, exist_ok=True)
    
    # Outputs
    base = os.path.splitext(os.path.basename(input_video))[0]
    output_video = os.path.join(output_dir, f"{base}_car_annotated.mp4")
    report_path = os.path.join(output_dir, f"{base}_car_report.txt")
    
    # Initialize components
    reader = init_reader()
    detector = init_detector(yolo_weights)
    vehicle_classes = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
    
    # Video IO
    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {input_video}")
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    
    # Detection logs
    vehicle_detections = {}
    plate_detections = {}
    frame_idx = 0
    
    # Track last seen frame for each vehicle to avoid duplicate logging
    last_seen_frames = {}
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            if frame_idx % max(1, int(frame_skip)) == 0:
                # Vehicle detection + tracking
                detections = detect_and_track_vehicles(frame, detector, vehicle_classes, conf_thresh=conf)
                
                for track_id, vehicle_type, (x1, y1, x2, y2) in detections:
                    # Draw bounding box with track ID
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{vehicle_type} ID:{track_id}",
                                (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                    
                    # Log vehicle detection - only if we haven't seen this vehicle recently
                    ts = _format_ts(frame_idx / max(fps, 1.0))
                    if track_id not in vehicle_detections:
                        vehicle_detections[track_id] = {
                            'type': vehicle_type,
                            'detections': [],
                            'plates': []
                        }
                        # First sighting - always log
                        vehicle_detections[track_id]['detections'].append(ts)
                        last_seen_frames[track_id] = frame_idx
                    else:
                        # Only log if we haven't seen this vehicle in the last 30 frames
                        # This prevents duplicate timestamps for the same continuous sighting
                        if frame_idx - last_seen_frames.get(track_id, 0) > 30:
                            vehicle_detections[track_id]['detections'].append(ts)
                            last_seen_frames[track_id] = frame_idx
                    
                    # License plate detection + recognition
                    plates = detect_and_recognize_plates(frame, reader)
                    for plate, (px, py, pw, ph) in plates:
                        if track_id not in plate_detections:
                            plate_detections[track_id] = []
                        
                        # Only add unique plates
                        existing_plates = [p['plate'] for p in plate_detections[track_id]]
                        if plate not in existing_plates:
                            plate_detections[track_id].append({
                                'plate': plate,
                                'timestamp': ts,
                                'position': (px, py, pw, ph)
                            })
                            # Add to vehicle's plate list (unique only)
                            if plate not in vehicle_detections[track_id]['plates']:
                                vehicle_detections[track_id]['plates'].append(plate)
                        
                        cv2.rectangle(frame, (px, py), (px+pw, py+ph), (0,0,255), 2)
                        cv2.putText(frame, plate, (px, py-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 2)
            
            writer.write(frame)
            
    finally:
        cap.release()
        writer.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
    
    # Count unique vehicles and plates
    total_vehicles = len(vehicle_detections)
    vehicles_with_plates = sum(1 for v in vehicle_detections.values() if v['plates'])
    total_plates = sum(len(v['plates']) for v in vehicle_detections.values())
    
    return {
        "output_video": output_video if os.path.exists(output_video) else None,
        "report_path": report_path if os.path.exists(report_path) else None,
        "vehicle_detections": vehicle_detections,
        "plate_detections": plate_detections,
        "total_vehicles": total_vehicles,
        "vehicles_with_plates": vehicles_with_plates,
        "total_plates": total_plates,
        "frames": frame_idx,
        "fps": float(fps),
        "width": int(width),
        "height": int(height),
    }
