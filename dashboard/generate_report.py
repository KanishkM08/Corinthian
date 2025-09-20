# generate_report.py

import io
import hashlib
import base64
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import pandas as pd
import json

def generate_report(report_data: dict, output_path: str):
    """
    Generate a comprehensive forensic analysis report in PDF format.
    
    report_data is a dict containing:
    {
        "report_id": str,                    # Unique report identifier
        "case_id": str,                      # Case identifier
        "investigator": str,                 # Investigator name
        "generating_system_version": str,    # System version
        "evidence_list": [                   # List of evidence files
            {
                "filename": str,
                "sha256": str,
                "ingest_time": str,
                "camera_id": str,
                "duration": str,
                "metadata": dict
            }
        ],
        "findings": [                        # Detection findings
            {
                "time_window": str,          # Format: "HH:MM:SS - HH:MM:SS"
                "track_id": str,
                "object_type": str,
                "representative_frame_path": str,  # Path to frame image
                "bounding_box": [x1, y1, x2, y2],
                "matched_offender_id": str,
                "matched_offender_name": str,
                "similarity_score": float,
                "verification_status": str   # "verified", "unverified", "pending"
            }
        ],
        "forensics": {                       # Forensic analysis results
            "metadata_summary": dict,        # Key metadata findings
            "tamper_flags": [                # Tampering detection results
                {
                    "time": str,             # Timestamp of tampering
                    "explanation": str       # Reason for flag
                }
            ],
            "deepfake_score": float          # Probability of deepfake (0-1)
        },
        "signatures": {                      # Digital signatures
            "report_sha256": str,            # Hash of this report
            "signature": str,                # Base64 encoded signature
            "signing_cert_subject": str,     # Certificate subject
            "signing_cert_pubkey_fingerprint": str  # Certificate fingerprint
        },
        "access_log_summary": {              # Access log information
            "total_accesses": int,
            "first_access": str,
            "last_access": str,
            "users": list                    # List of users who accessed
        }
    }
    """

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    # Define custom styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12
    )
    normal_style = styles['Normal']
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold'
    )
    
    # --- Report Header ---
    story.append(Paragraph("DIGITAL FORENSIC ANALYSIS REPORT", title_style))
    story.append(Spacer(1, 12))
    
    # --- Report Metadata ---
    story.append(Paragraph("Report Metadata", heading_style))
    
    report_meta_data = [
        ["Report ID:", report_data.get('report_id', 'N/A')],
        ["Generation Time (UTC):", datetime.utcnow().isoformat() + 'Z'],
        ["Generating System Version:", report_data.get('generating_system_version', 'N/A')],
        ["Case ID:", report_data.get('case_id', 'N/A')],
        ["Investigator:", report_data.get('investigator', 'N/A')]
    ]
    
    report_meta_table = Table(report_meta_data, colWidths=[2*inch, 3*inch])
    report_meta_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    story.append(report_meta_table)
    story.append(Spacer(1, 12))
    
    # --- Evidence List ---
    story.append(Paragraph("Evidence List", heading_style))
    
    evidence_list = report_data.get('evidence_list', [])
    if evidence_list:
        evidence_data = [['Filename', 'SHA256', 'Ingest Time', 'Camera ID', 'Duration']]
        for evidence in evidence_list:
            evidence_data.append([
                evidence.get('filename', 'N/A'),
                evidence.get('sha256', 'N/A')[:16] + '...' if evidence.get('sha256') else 'N/A',
                evidence.get('ingest_time', 'N/A'),
                evidence.get('camera_id', 'N/A'),
                evidence.get('duration', 'N/A')
            ])
        
        evidence_table = Table(evidence_data, colWidths=[1.2*inch, 1.2*inch, 1.2*inch, 0.8*inch, 0.8*inch])
        evidence_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(evidence_table)
    else:
        story.append(Paragraph("No evidence data available", normal_style))
    story.append(Spacer(1, 12))
    
    # --- Findings ---
    story.append(Paragraph("Findings", heading_style))
    
    findings = report_data.get('findings', [])
    if findings:
        findings_data = [['Time Window', 'Track ID', 'Object Type', 'Matched Offender', 'Similarity', 'Status']]
        for finding in findings:
            offender_info = f"{finding.get('matched_offender_id', 'N/A')}"
            if finding.get('matched_offender_name'):
                offender_info += f" ({finding.get('matched_offender_name')})"
                
            findings_data.append([
                finding.get('time_window', 'N/A'),
                finding.get('track_id', 'N/A'),
                finding.get('object_type', 'N/A'),
                offender_info,
                f"{finding.get('similarity_score', 0)*100:.1f}%" if finding.get('similarity_score') else 'N/A',
                finding.get('verification_status', 'N/A')
            ])
        
        findings_table = Table(findings_data, colWidths=[1*inch, 0.6*inch, 0.8*inch, 1.2*inch, 0.6*inch, 0.8*inch])
        findings_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(findings_table)
    else:
        story.append(Paragraph("No findings detected", normal_style))
    story.append(Spacer(1, 12))
    
    # --- Forensics ---
    story.append(Paragraph("Forensic Analysis", heading_style))
    
    forensics = report_data.get('forensics', {})
    
    # Metadata Summary
    story.append(Paragraph("Metadata Summary", bold_style))
    metadata_summary = forensics.get('metadata_summary', {})
    if metadata_summary:
        metadata_text = json.dumps(metadata_summary, indent=2)
        story.append(Paragraph(metadata_text, normal_style))
    else:
        story.append(Paragraph("No metadata summary available", normal_style))
    
    story.append(Spacer(1, 6))
    
    # Tamper Flags
    story.append(Paragraph("Tamper Detection", bold_style))
    tamper_flags = forensics.get('tamper_flags', [])
    if tamper_flags:
        for flag in tamper_flags:
            story.append(Paragraph(f"Time: {flag.get('time', 'N/A')} - {flag.get('explanation', 'No explanation')}", normal_style))
    else:
        story.append(Paragraph("No tampering detected", normal_style))
    
    story.append(Spacer(1, 6))
    
    # Deepfake Score
    deepfake_score = forensics.get('deepfake_score')
    if deepfake_score is not None:
        story.append(Paragraph(f"Deepfake Detection Score: {deepfake_score*100:.1f}%", bold_style))
        if deepfake_score > 0.7:
            story.append(Paragraph("WARNING: High probability of deepfake manipulation", normal_style))
        elif deepfake_score > 0.3:
            story.append(Paragraph("Moderate probability of deepfake manipulation", normal_style))
        else:
            story.append(Paragraph("Low probability of deepfake manipulation", normal_style))
    else:
        story.append(Paragraph("Deepfake analysis not performed", normal_style))
    
    story.append(Spacer(1, 12))
    
    # --- Signatures ---
    story.append(Paragraph("Digital Signatures", heading_style))
    
    signatures = report_data.get('signatures', {})
    signature_data = [
        ["Report SHA256:", signatures.get('report_sha256', 'N/A')],
        ["Signature:", signatures.get('signature', 'N/A')[:50] + '...' if signatures.get('signature') else 'N/A'],
        ["Certificate Subject:", signatures.get('signing_cert_subject', 'N/A')],
        ["Certificate Fingerprint:", signatures.get('signing_cert_pubkey_fingerprint', 'N/A')]
    ]
    
    signature_table = Table(signature_data, colWidths=[1.5*inch, 4*inch])
    signature_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 12))
    
    # --- Access Log Summary ---
    story.append(Paragraph("Access Log Summary", heading_style))
    
    access_log = report_data.get('access_log_summary', {})
    if access_log:
        access_data = [
            ["Total Accesses:", str(access_log.get('total_accesses', 'N/A'))],
            ["First Access:", access_log.get('first_access', 'N/A')],
            ["Last Access:", access_log.get('last_access', 'N/A')],
            ["Users:", ", ".join(access_log.get('users', [])) if access_log.get('users') else 'N/A']
        ]
        
        access_table = Table(access_data, colWidths=[1.5*inch, 4*inch])
        access_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ]))
        story.append(access_table)
    else:
        story.append(Paragraph("No access log data available", normal_style))
    
    story.append(Spacer(1, 12))
    story.append(Paragraph("End of Report", heading_style))
    
    # Calculate report hash (for the signatures section)
    # This would normally be calculated from the final report content
    # For now, we'll generate a placeholder
    report_content = "\n".join([str(item) for item in story])
    report_hash = hashlib.sha256(report_content.encode()).hexdigest()
    report_data['signatures']['report_sha256'] = report_hash

    # Build PDF
    doc.build(story)

    # Write to file
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    return output_path