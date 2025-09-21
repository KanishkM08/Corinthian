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
    
    # Break very long words or continuous strings
    if len(text) > 80:
        words = text.split()
        safe_words = []
        for word in words:
            if len(word) > 60:  # Break very long words
                # Split long words into chunks
                chunks = [word[i:i+50] for i in range(0, len(word), 50)]
                safe_words.extend(chunks)
            else:
                safe_words.append(word)
        text = " ".join(safe_words)
    
    return Paragraph(text, style)


def generate_report(report_data: dict, output_path: str):
    """
    Generate a comprehensive forensic analysis report in PDF format.
    report_data is a dict with keys including report_id, case_id, investigator,
    generating_system_version, evidence_list, findings, forensics, signatures, access_log_summary.
    """
    
    # --- STEP 1: Build story array with ALL content EXCEPT digital signatures ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    story = []

    # Styles with proper widths
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER,
        wordWrap='CJK'
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12,
        wordWrap='CJK'
    )
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
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
    story.append(Spacer(1, 12))

    # --- Report Metadata ---
    story.append(safe_paragraph("Report Metadata", heading_style))
    report_meta_data = [
        ["Report ID:", report_data.get('report_id', 'N/A')],
        ["Generation Time (UTC):", datetime.utcnow().isoformat() + 'Z'],
        ["Generating System Version:", report_data.get('generating_system_version', 'N/A')],
        ["Case ID:", report_data.get('case_id', 'N/A')],
        ["Investigator:", report_data.get('investigator', 'N/A')]
    ]
    
    # Use smaller column widths
    report_meta_table = Table(report_meta_data, colWidths=[1.8*inch, 3.2*inch])
    report_meta_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))
    story.append(report_meta_table)
    story.append(Spacer(1, 12))

    # --- Evidence List ---
    story.append(safe_paragraph("Evidence List", heading_style))
    evidence_list = report_data.get('evidence_list', [])
    if evidence_list:
        for idx, evidence in enumerate(evidence_list, 1):
            story.append(Spacer(1, 6))
            story.append(safe_paragraph(f"Evidence Item {idx}:", bold_style))
            
            # Create evidence details as a table
            evidence_data = [
                ["Filename:", str(evidence.get('filename', 'N/A'))],
                ["SHA256:", str(evidence.get('sha256', 'N/A'))],
                ["Ingest Time:", str(evidence.get('ingest_time', 'N/A'))],
                ["Camera ID:", str(evidence.get('camera_id', 'N/A'))],
        
            ]
            
            evidence_table = Table(evidence_data, colWidths=[1.2*inch, 3.8*inch])
            evidence_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (0, 0), (-1, -1), True)
            ]))
            story.append(evidence_table)
    else:
        story.append(safe_paragraph("No evidence data available", normal_style))
    story.append(Spacer(1, 12))

    # --- Findings ---
    story.append(safe_paragraph("Findings", heading_style))
    findings = report_data.get('findings', [])
    if findings:
        findings_data = [["Time", "Object Type", "Matched Offender", "Similarity", "Status"]]
        for finding in findings:
            offender_info = str(finding.get('matched_offender_id', 'N/A'))
            if finding.get('matched_offender_name'):
                offender_info += f" ({finding.get('matched_offender_name')})"

            # Truncate long offender info if needed
            if len(offender_info) > 25:
                offender_info = offender_info[:22] + "..."

            # Format similarity score appropriately
            similarity = finding.get('similarity_score', 0)
            if finding.get('object_type') == 'Person':
                similarity_str = f"{similarity*100:.1f}%" if similarity else 'N/A'
            else:
                # For vehicles, show a simplified score
                similarity_str = "Plate Found" if similarity > 0.7 else "No Plate"

            findings_data.append([
                str(finding.get('time_window', 'N/A')),
                str(finding.get('object_type', 'N/A')),
                offender_info,
                similarity_str,
                str(finding.get('verification_status', 'N/A'))
            ])
        
        findings_table = Table(
            findings_data,
            colWidths=[1.0*inch, 1.0*inch, 1.6*inch, 0.8*inch, 0.8*inch]
        )
        findings_table.setStyle(TableStyle([
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
        story.append(findings_table)
    else:
        story.append(safe_paragraph("No findings detected", normal_style))
    story.append(Spacer(1, 12))

    # --- Forensic Analysis ---
    story.append(safe_paragraph("Forensic Analysis", heading_style))
    forensics = report_data.get('forensics', {})
    
    story.append(safe_paragraph("Metadata Summary", bold_style))
    metadata_summary = forensics.get('metadata_summary', {})
    if metadata_summary:
        # Format JSON data properly to avoid layout issues
        try:
            metadata_text = json.dumps(metadata_summary, indent=2)
            # Break long lines in JSON
            lines = metadata_text.split('\n')
            formatted_lines = []
            for line in lines:
                if len(line) > 70:
                    # Break long lines at appropriate points
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line + word) > 70:
                            formatted_lines.append(current_line)
                            current_line = "  " + word + " "
                        else:
                            current_line += word + " "
                    if current_line:
                        formatted_lines.append(current_line)
                else:
                    formatted_lines.append(line)
            metadata_text = '\n'.join(formatted_lines)
            story.append(safe_paragraph(metadata_text.replace('\n', '<br/>'), normal_style))
        except Exception:
            story.append(safe_paragraph("Metadata summary formatting error", normal_style))
    else:
        story.append(safe_paragraph("No metadata summary available", normal_style))
    
    story.append(Spacer(1, 6))
    story.append(safe_paragraph("Tamper Detection", bold_style))
    tamper_flags = forensics.get('tamper_flags', [])
    if tamper_flags:
        for flag in tamper_flags:
            flag_time = str(flag.get('time', 'N/A'))
            flag_explanation = str(flag.get('explanation', 'No explanation'))
            tamper_text = f"Time: {flag_time} - {flag_explanation}"
            story.append(safe_paragraph(tamper_text, normal_style))
    else:
        story.append(safe_paragraph("No tampering detected", normal_style))
    story.append(Spacer(1, 6))

    # deepfake_score = forensics.get('deepfake_score')
    # if deepfake_score is not None:
    #     story.append(safe_paragraph(f"Deepfake Detection Score: {deepfake_score*100:.1f}%", bold_style))
    #     if deepfake_score > 0.7:
    #         story.append(safe_paragraph("WARNING: High probability of deepfake manipulation", normal_style))
    #     elif deepfake_score > 0.3:
    #         story.append(safe_paragraph("Moderate probability of deepfake manipulation", normal_style))
    #     else:
    #         story.append(safe_paragraph("Low probability of deepfake manipulation", normal_style))
    # else:
    #     story.append(safe_paragraph("Deepfake analysis not performed", normal_style))
    # story.append(Spacer(1, 12))

    # Create a temporary story for hash calculation (without signatures)
    temp_story = story.copy()
    temp_story.append(safe_paragraph("End of Report", heading_style))
    
    temp_buffer = io.BytesIO()
    temp_doc = SimpleDocTemplate(
        temp_buffer, 
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    temp_doc.build(temp_story)
    temp_pdf_bytes = temp_buffer.getvalue()
    report_hash = hashlib.sha256(temp_pdf_bytes).hexdigest()

    # Generate digital signatures
    if 'signatures' not in report_data:
        report_data['signatures'] = {}
    report_data['signatures']['report_sha256'] = report_hash

    try:
        key_path = "private_key.pem"
        cert_path = "certificate.crt"
        if os.path.exists(key_path) and os.path.exists(cert_path):
            with open(key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        else:
            private_key, cert = generate_self_signed_cert()

        signature = private_key.sign(
            report_hash.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        report_data['signatures']['signature'] = signature.hex()
        report_data['signatures']['signing_cert_subject'] = cert.subject.rfc4514_string()
        report_data['signatures']['signing_cert_pubkey_fingerprint'] = cert.fingerprint(hashes.SHA256()).hex()

    except Exception as e:
        print("Error signing report:", e)
        report_data['signatures'].setdefault('signature', 'N/A')
        report_data['signatures'].setdefault('signing_cert_subject', 'N/A')
        report_data['signatures'].setdefault('signing_cert_pubkey_fingerprint', 'N/A')

    # Add digital signatures and access log to story
    story.append(safe_paragraph("Digital Signatures", heading_style))
    signatures = report_data['signatures']
    
    # Handle long signature strings
    signature_val = signatures.get('signature', 'N/A')
    if len(signature_val) > 50:
        signature_display = signature_val[:50] + '...'
    else:
        signature_display = signature_val
    
    signature_data = [
        ["Report SHA256:", str(signatures.get('report_sha256', 'N/A'))],
        ["Signature:", signature_display],
        ["Certificate Subject:", str(signatures.get('signing_cert_subject', 'N/A'))],
        ["Certificate Fingerprint:", str(signatures.get('signing_cert_pubkey_fingerprint', 'N/A'))],
    ]
    
    signature_table = Table(signature_data, colWidths=[1.4*inch, 3.6*inch])
    signature_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 12))

    # --- Access Log ---
    story.append(safe_paragraph("Access Log Summary", heading_style))
    access_log = report_data.get('access_log_summary', {})
    if access_log:
        users_list = access_log.get('users', [])
        users_str = ", ".join(users_list) if users_list else 'N/A'
        if len(users_str) > 50:
            users_str = users_str[:47] + "..."
            
        access_data = [
            ["Total Accesses:", str(access_log.get('total_accesses', 'N/A'))],
            ["First Access:", str(access_log.get('first_access', 'N/A'))],
            ["Last Access:", str(access_log.get('last_access', 'N/A'))],
            ["Users:", users_str],
        ]
        access_table = Table(access_data, colWidths=[1.4*inch, 3.6*inch])
        access_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (0, 0), (-1, -1), True)
        ]))
        story.append(access_table)
    else:
        story.append(safe_paragraph("No access log data available", normal_style))
    story.append(Spacer(1, 12))

    story.append(safe_paragraph("End of Report", heading_style))

    # Build final complete PDF
    final_buffer = io.BytesIO()
    final_doc = SimpleDocTemplate(
        final_buffer, 
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    final_doc.build(story)
    
    # Save to file
    with open(output_path, "wb") as f:
        f.write(final_buffer.getvalue())

    return output_path
