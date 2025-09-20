# generate_report.py

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

def generate_report(report_data: dict, output_path: str):

    """
    report_data is a dict like:
    {
        "report_id": "...",
        "case_id": "...",
        "investigator": "...",
        "evidence_list": [
            {
                "filename": ...,
                "sha256": ...,
                "ingest_time": ...,
                "camera_id": ...,
                "duration": ...,
                "metadata": {...}
            },
            ...
        ],
        "tamper_events": [12.3, 45.6]  # timestamps in seconds
    }
    """

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    # --- Report Header ---
    story.append(Paragraph(f"Report ID: {report_data['report_id']}", styles["Normal"]))
    story.append(Paragraph(f"Case ID: {report_data['case_id']}", styles["Normal"]))
    story.append(Paragraph(f"Investigator: {report_data['investigator']}", styles["Normal"]))
    story.append(Paragraph(f"Generation Time (UTC): {datetime.utcnow().isoformat()}Z", styles["Normal"]))
    story.append(Spacer(1, 12))

    # --- Evidence List as dictionary column form ---
    story.append(Paragraph("Evidence List", styles["Heading2"]))

    for evidence in report_data.get("evidence_list", []):
        story.append(Paragraph(f"Filename: {evidence.get('filename', '')}", styles["Normal"]))
        story.append(Paragraph(f"SHA256: {evidence.get('sha256', '')}", styles["Normal"]))
        story.append(Paragraph(f"Ingest Time: {evidence.get('ingest_time', '')}", styles["Normal"]))
        story.append(Paragraph(f"Camera ID: {evidence.get('camera_id', '')}", styles["Normal"]))
        story.append(Paragraph(f"Duration (H:M:S): {evidence.get('duration', '')}", styles["Normal"]))
        story.append(Spacer(1, 12))  # space between evidence entries

    # --- Tamper Events ---
    story.append(Paragraph("Tamper Events", styles["Heading2"]))

    if report_data.get("tamper_events"):
        for idx, t_event in enumerate(report_data["tamper_events"], 1):
            story.append(Paragraph(f"Event {idx}: Tampering detected at {t_event:.2f} seconds", styles["Normal"]))
    else:
        story.append(Paragraph("No tampering detected", styles["Normal"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("End of Report", styles["Heading2"]))

    # Build PDF
    doc.build(story)

    # Write to file
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    return output_path
