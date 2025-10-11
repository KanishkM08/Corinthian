import io
import os
import hashlib
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus.tableofcontents import TableOfContents
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from src.car_detection import run_car_detection


def generate_self_signed_cert():
    """Generate a temporary self-signed key/certificate for fallback"""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Goa"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Goa"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Corinthian Hackathon"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"corinthian.local"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow().replace(year=datetime.utcnow().year + 1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256(), default_backend())
    )
    return key, cert


def safe_paragraph(text, style, max_width=None):
    """Create a paragraph with safe text wrapping"""
    if not text:
        text = "N/A"
    
    # Ensure text is a string and handle long lines
    text = str(text)
    
    # Break very long words or continuous strings more aggressively
    if len(text) > 60:
        words = text.split()
        safe_words = []
        for word in words:
            if len(word) > 40:  # Break very long words more aggressively
                # Split long words into smaller chunks
                chunks = [word[i:i+30] for i in range(0, len(word), 30)]
                safe_words.extend(chunks)
            else:
                safe_words.append(word)
        text = " ".join(safe_words)
    
    # Add line breaks for very long continuous text
    if len(text) > 80 and ' ' not in text:
        text = '<br/>'.join([text[i:i+60] for i in range(0, len(text), 60)])
    
    return Paragraph(text, style)


def generate_report(report_data: dict, output_path: str):
    """
    Generate a comprehensive forensic analysis report in PDF format.
    """
    
    # --- STEP 1: Build story array with ALL content EXCEPT digital signatures ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=40,  # Reduced margins for more space
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    story = []

    # Styles with proper widths and word wrap
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,  # Reduced font size
        spaceAfter=20,
        alignment=TA_CENTER,
        wordWrap='CJK'
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,  # Reduced font size
        spaceAfter=10,
        spaceBefore=10,
        wordWrap='CJK'
    )
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=9,  # Reduced font size
        alignment=TA_LEFT,
        wordWrap='CJK',
        allowWidows=1,
        allowOrphans=1
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=normal_style,
        fontName='Helvetica-Bold',
        wordWrap='CJK'
    )

    # --- Report Header ---
    story.append(safe_paragraph("DIGITAL FORENSIC ANALYSIS REPORT", title_style))
    story.append(Spacer(1, 10))

    # --- Report Metadata ---
    story.append(safe_paragraph("Report Metadata", heading_style))
    report_meta_data = [
        ["Report ID:", report_data.get('report_id', 'N/A')],
        ["Case ID:", report_data.get('case_id', 'N/A')],
        ["Investigator:", report_data.get('investigator', 'N/A')],
        ["Generation Time:", datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')],
        ["System Version:", report_data.get('generating_system_version', 'N/A')]
    ]
    
    # Use smaller column widths
    report_meta_table = Table(report_meta_data, colWidths=[1.5*inch, 3.5*inch])
    report_meta_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))
    story.append(report_meta_table)
    story.append(Spacer(1, 10))

    # --- Evidence List ---
    story.append(safe_paragraph("Evidence List", heading_style))
    evidence_list = report_data.get('evidence_list', [])
    if evidence_list:
        evidence_data = [["Filename", "SHA256", "Camera ID", "Ingest Time"]]
        for evidence in evidence_list:
            filename = str(evidence.get('filename', 'N/A'))
            sha256 = str(evidence.get('sha256', 'N/A'))
            camera_id = str(evidence.get('camera_id', 'N/A'))
            ingest_time = str(evidence.get('ingest_time', 'N/A'))
            
            # Truncate long values
            if len(sha256) > 20:
                sha256 = sha256[:17] + "..."
            if len(ingest_time) > 15:
                ingest_time = ingest_time[:12] + "..."
                
            evidence_data.append([filename, sha256, camera_id, ingest_time])
        
        evidence_table = Table(evidence_data, colWidths=[1.2*inch, 1.5*inch, 0.8*inch, 1.5*inch])
        evidence_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(evidence_table)
    else:
        story.append(safe_paragraph("No evidence data available", normal_style))
    story.append(Spacer(1, 10))

    # --- Findings ---
    story.append(safe_paragraph("Findings", heading_style))
    findings = report_data.get('findings', [])
    if findings:
        findings_data = [["Time", "Object", "Matched ID", "Score", "Status"]]
        
        # Separate vehicles and persons for better organization
        vehicle_findings = [f for f in findings if f.get('object_type') != 'Person']
        person_findings = [f for f in findings if f.get('object_type') == 'Person']
        
        # Add vehicle findings first
        for finding in vehicle_findings:
            time_window = str(finding.get('time_window', 'N/A'))
            object_type = str(finding.get('object_type', 'N/A'))
            offender_id = str(finding.get('matched_offender_id', 'N/A'))
            status = str(finding.get('verification_status', 'N/A'))
            
            # Format similarity score for vehicles
            similarity = finding.get('similarity_score', 0)
            score_str = "Plate" if similarity > 0.7 else "No Plate"

            # Truncate long values
            if len(time_window) > 10:
                time_window = time_window[:8] + "..."
            if len(offender_id) > 12:
                offender_id = offender_id[:9] + "..."
            if len(object_type) > 8:
                object_type = object_type[:6] + "..."
                
            findings_data.append([time_window, object_type, offender_id, score_str, status])
        
        # Add person findings
        for finding in person_findings:
            time_window = str(finding.get('time_window', 'N/A'))
            object_type = str(finding.get('object_type', 'N/A'))
            offender_id = str(finding.get('matched_offender_id', 'N/A'))
            status = str(finding.get('verification_status', 'N/A'))
            
            # Format similarity score for persons
            similarity = finding.get('similarity_score', 0)
            score_str = f"{similarity*100:.1f}%" if similarity else 'N/A'

            # Truncate long values
            if len(time_window) > 10:
                time_window = time_window[:8] + "..."
            if len(offender_id) > 12:
                offender_id = offender_id[:9] + "..."
            if len(object_type) > 8:
                object_type = object_type[:6] + "..."
                
            findings_data.append([time_window, object_type, offender_id, score_str, status])
        
        findings_table = Table(
            findings_data,
            colWidths=[0.8*inch, 0.7*inch, 1.0*inch, 0.7*inch, 0.8*inch]
        )
        findings_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(findings_table)
    else:
        story.append(safe_paragraph("No findings detected", normal_style))
    story.append(Spacer(1, 10))

    # --- Forensic Analysis ---
    story.append(safe_paragraph("Forensic Analysis", heading_style))
    forensics = report_data.get('forensics', {})
    
    # Metadata Summary
    story.append(safe_paragraph("Metadata Summary", bold_style))
    metadata_summary = forensics.get('metadata_summary', {})
    if metadata_summary:
        # Select only key metadata to avoid overcrowding
        key_metadata = [
            ["Frame Count", metadata_summary.get('frame_count', 'N/A')],
            ["FPS", metadata_summary.get('fps', 'N/A')],
            ["Duration", metadata_summary.get('duration_hms', 'N/A')],
            ["Resolution", f"{metadata_summary.get('width', 'N/A')}x{metadata_summary.get('height', 'N/A')}"],
            ["File Size", f"{metadata_summary.get('file_size_bytes', 0) / (1024*1024):.1f} MB"],
        ]
        
        meta_table = Table(key_metadata, colWidths=[1.5*inch, 1.0*inch])
        meta_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(meta_table)
    else:
        story.append(safe_paragraph("No metadata summary available", normal_style))
    
    story.append(Spacer(1, 6))
    
    # Tamper Detection
    story.append(safe_paragraph("Tamper Detection", bold_style))
    tamper_flags = forensics.get('tamper_flags', [])
    if tamper_flags:
        tamper_data = [["Time", "Event"]]
        for flag in tamper_flags[:10]:  # Limit to first 10 events
            flag_time = str(flag.get('time', 'N/A'))
            flag_explanation = str(flag.get('explanation', 'Tampering'))
            
            # Truncate long values
            if len(flag_time) > 10:
                flag_time = flag_time[:8] + "..."
            if len(flag_explanation) > 25:
                flag_explanation = flag_explanation[:22] + "..."
                
            tamper_data.append([flag_time, flag_explanation])
        
        if len(tamper_flags) > 10:
            tamper_data.append([f"+{len(tamper_flags)-10} more", "events"])
        
        tamper_table = Table(tamper_data, colWidths=[1.0*inch, 3.0*inch])
        tamper_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(tamper_table)
    else:
        story.append(safe_paragraph("No tampering detected", normal_style))
    story.append(Spacer(1, 10))

    # --- Car Detection Summary ---
    car_detection = report_data.get('car_detection', {})
    if car_detection and car_detection.get('total_vehicles', 0) > 0:
        story.append(safe_paragraph("Vehicle Detection Summary", heading_style))
        
        car_summary_data = [
            ["Total Vehicles", car_detection.get('total_vehicles', 0)],
            ["Vehicles with Plates", car_detection.get('vehicles_with_plates', 0)],
            ["Total Plates Found", car_detection.get('total_plates', 0)]
        ]
        
        car_table = Table(car_summary_data, colWidths=[2.0*inch, 1.0*inch])
        car_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(car_table)
        story.append(Spacer(1, 10))

    # Create a temporary story for hash calculation (without signatures)
    temp_story = story.copy()
    
    # Add digital signatures and access log
    story.append(safe_paragraph("Digital Signatures", heading_style))
    signatures = report_data.get('signatures', {})
    
    signature_data = [
        ["Report SHA256:", str(signatures.get('report_sha256', 'N/A'))[:50] + "..."],
        ["Certificate Subject:", str(signatures.get('signing_cert_subject', 'N/A'))[:40] + "..."],
    ]
    
    signature_table = Table(signature_data, colWidths=[1.5*inch, 3.5*inch])
    signature_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 10))

    # --- Access Log ---
    story.append(safe_paragraph("Access Log Summary", heading_style))
    access_log = report_data.get('access_log_summary', {})
    if access_log:
        users_list = access_log.get('users', [])
        users_str = ", ".join(users_list) if users_list else 'N/A'
        if len(users_str) > 40:
            users_str = users_str[:37] + "..."
            
        access_data = [
            ["Total Accesses:", str(access_log.get('total_accesses', 'N/A'))],
            ["First Access:", str(access_log.get('first_access', 'N/A'))[:20]],
            ["Last Access:", str(access_log.get('last_access', 'N/A'))[:20]],
            ["Users:", users_str],
        ]
        access_table = Table(access_data, colWidths=[1.5*inch, 3.5*inch])
        access_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(access_table)
    else:
        story.append(safe_paragraph("No access log data available", normal_style))
    
    story.append(Spacer(1, 10))
    story.append(safe_paragraph("End of Report", heading_style))

    # Build final complete PDF
    final_buffer = io.BytesIO()
    final_doc = SimpleDocTemplate(
        final_buffer, 
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    try:
        final_doc.build(story)
    except Exception as e:
        # Fallback: Try with even smaller fonts
        for style in [title_style, heading_style, normal_style, bold_style]:
            style.fontSize -= 1
        final_doc.build(story)
    
    # Save to file
    with open(output_path, "wb") as f:
        f.write(final_buffer.getvalue())

    return output_path
