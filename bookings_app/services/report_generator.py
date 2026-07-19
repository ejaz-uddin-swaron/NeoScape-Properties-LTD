"""
Referencing Report PDF Generator using WeasyPrint.

Renders a professional HTML template with the referencing check results
and compiles it into a PDF document stored in Supabase Storage or locally.
"""
import logging
from datetime import datetime
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def generate_referencing_report_html(app) -> str:
    """Build the full HTML string for the referencing PDF report."""

    # Decision display mapping
    decision_map = {
        'approve': ('APPROVED', '#16a34a', 'This applicant has passed all automated referencing checks.'),
        'caution': ('APPROVED WITH CONDITIONS', '#d97706', 'This applicant is conditionally approved. A guarantor may be required.'),
        'decline': ('DECLINED', '#dc2626', 'This applicant has failed one or more critical referencing checks.'),
        'pending': ('PENDING REVIEW', '#6b7280', 'Automated checks are complete but a final decision has not been made.'),
    }
    decision_label, decision_color, decision_summary = decision_map.get(
        app.decision, decision_map['pending']
    )

    # Credit score colour
    score = app.credit_score
    if score is not None:
        if score >= 650:
            score_color = '#16a34a'
        elif score >= 550:
            score_color = '#d97706'
        else:
            score_color = '#dc2626'
    else:
        score_color = '#6b7280'

    # AI explanation
    ai_explanation = ''
    if app.ai_raw_check_result and isinstance(app.ai_raw_check_result, dict):
        ai_explanation = app.ai_raw_check_result.get('explanation', '')

    # Application data fields
    app_data = app.application_data or {}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm 2.5cm;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1a1a1a;
    line-height: 1.55;
    background: #fff;
  }}
  .header {{
    text-align: center;
    padding-bottom: 18px;
    border-bottom: 3px solid #111;
    margin-bottom: 24px;
  }}
  .header h1 {{
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #111;
  }}
  .header p {{
    font-size: 9pt;
    color: #666;
    margin-top: 4px;
  }}
  .decision-banner {{
    padding: 14px 20px;
    border-radius: 8px;
    text-align: center;
    margin-bottom: 24px;
    color: #fff;
    background: {decision_color};
  }}
  .decision-banner h2 {{
    font-size: 16pt;
    font-weight: 700;
    margin-bottom: 2px;
  }}
  .decision-banner p {{
    font-size: 9pt;
    opacity: 0.9;
  }}
  .section {{
    margin-bottom: 20px;
  }}
  .section-title {{
    font-size: 10pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #555;
    border-bottom: 1px solid #ddd;
    padding-bottom: 4px;
    margin-bottom: 10px;
  }}
  .grid {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }}
  .grid .card {{
    flex: 1;
    min-width: 140px;
    padding: 12px 16px;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    text-align: center;
  }}
  .card .label {{
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #888;
    margin-bottom: 4px;
  }}
  .card .value {{
    font-size: 20pt;
    font-weight: 800;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
  }}
  table th, table td {{
    text-align: left;
    padding: 7px 10px;
    font-size: 10pt;
    border-bottom: 1px solid #eee;
  }}
  table th {{
    font-weight: 600;
    color: #555;
    width: 35%;
  }}
  .notes {{
    padding: 10px 14px;
    background: #f7f7f7;
    border-radius: 6px;
    font-size: 9.5pt;
    color: #444;
    white-space: pre-wrap;
  }}
  .footer {{
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid #ddd;
    text-align: center;
    font-size: 8pt;
    color: #999;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>TENANT REFERENCING REPORT</h1>
  <p>NeoScape Properties Ltd &middot; Confidential &middot; Generated {datetime.now().strftime('%d %B %Y at %H:%M')}</p>
</div>

<div class="decision-banner">
  <h2>{decision_label}</h2>
  <p>{decision_summary}</p>
</div>

<div class="section">
  <div class="section-title">Applicant Information</div>
  <table>
    <tr><th>Full Name</th><td>{app.applicant_name}</td></tr>
    <tr><th>Email</th><td>{app.applicant_email}</td></tr>
    <tr><th>Phone</th><td>{app.applicant_phone or 'Not provided'}</td></tr>
    <tr><th>Property</th><td>{app.property_room.name} &mdash; {app.property_room.location}</td></tr>
    <tr><th>Application Date</th><td>{app.created_at.strftime('%d %B %Y')}</td></tr>
  </table>
</div>

<div class="section">
  <div class="section-title">Financial &amp; Credit Assessment</div>
  <div class="grid">
    <div class="card">
      <div class="label">Credit Score</div>
      <div class="value" style="color:{score_color}">{score if score is not None else 'N/A'}</div>
    </div>
    <div class="card">
      <div class="label">CCJ / IVA / Bankruptcy</div>
      <div class="value" style="color:{'#dc2626' if app.ccj_iva_found else '#16a34a'}">{'Found' if app.ccj_iva_found else 'None'}</div>
    </div>
    <div class="card">
      <div class="label">Missed Payments</div>
      <div class="value" style="color:{'#dc2626' if app.missed_payments >= 3 else '#d97706' if app.missed_payments > 0 else '#16a34a'}">{app.missed_payments}</div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Employment &amp; Residential Details</div>
  <table>
    <tr><th>Employer</th><td>{app_data.get('employer_name', 'Not provided')}</td></tr>
    <tr><th>Employer Contact</th><td>{app_data.get('employer_contact', 'Not provided')}</td></tr>
    <tr><th>Annual Salary</th><td>&pound;{app_data.get('annual_salary', 'Not provided')}</td></tr>
    <tr><th>Current Landlord</th><td>{app_data.get('current_landlord_name', 'Not provided')}</td></tr>
    <tr><th>Landlord Contact</th><td>{app_data.get('current_landlord_contact', 'Not provided')}</td></tr>
  </table>
</div>

{'<div class="section"><div class="section-title">Address History</div><div class="notes">' + str(app_data.get('address_history', '')) + '</div></div>' if app_data.get('address_history') else ''}

{'<div class="section"><div class="section-title">AI Analysis Summary</div><div class="notes">' + ai_explanation + '</div></div>' if ai_explanation else ''}

{'<div class="section"><div class="section-title">Landlord Override Notes</div><div class="notes">' + app.landlord_override_notes + '</div></div>' if app.landlord_override_notes else ''}

<div class="footer">
  This report was generated automatically by NeoScape Properties Ltd.<br>
  Report Reference: REF-{app.id:05d} &middot; Application Token: {app.token[:12]}...
</div>

</body>
</html>"""
    return html
def generate_referencing_report_pdf(app):
    """
    Generate the referencing PDF report for a given ReferencingApplication instance.
    Returns the file URL where the PDF is stored.
    """
    import io
    from xhtml2pdf import pisa

    html_content = generate_referencing_report_html(app)
    
    # Render PDF using xhtml2pdf in-memory
    pdf_stream = io.BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_stream)
    
    if pisa_status.err:
        raise RuntimeError("Failed to render PDF using xhtml2pdf")
        
    pdf_bytes = pdf_stream.getvalue()

    # Try to upload to Supabase Storage (private bucket), fallback to local
    try:
        from core.storage_backends import supabase_storage
        import uuid

        if supabase_storage.client:
            file_name = f"referencing_report_{app.id}_{uuid.uuid4().hex[:8]}.pdf"
            file_path = f"referencing_reports/{file_name}"

            supabase_storage._ensure_bucket('documents', public=False)
            storage = supabase_storage.client.storage.from_('documents')

            try:
                storage.upload(
                    path=file_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf"}
                )
            except TypeError:
                storage.upload(
                    path=file_path,
                    data=pdf_bytes,
                    file_options={"content-type": "application/pdf"}
                )

            signed_url = supabase_storage.create_signed_url(file_path, bucket_name='documents', expires_in=86400)
            # Store the raw file path (not the expiring signed URL) so we can
            # regenerate fresh signed URLs on demand via the download endpoint.
            app.report_pdf_url = file_path
            app.save(update_fields=['report_pdf_url'])
            logger.info("PDF report uploaded to Supabase for application #%s", app.id)
            # Return the signed URL for immediate use
            return signed_url or file_path
    except Exception as e:
        logger.warning("Supabase upload failed for PDF report, falling back to local: %s", e)

    # Fallback: save locally
    import os
    from django.conf import settings

    reports_dir = os.path.join(settings.MEDIA_ROOT, 'referencing_reports')
    os.makedirs(reports_dir, exist_ok=True)
    file_name = f"referencing_report_{app.id}.pdf"
    file_path = os.path.join(reports_dir, file_name)

    with open(file_path, 'wb') as f:
        f.write(pdf_bytes)

    relative_url = f"{settings.MEDIA_URL}referencing_reports/{file_name}"
    app.report_pdf_url = relative_url
    app.save(update_fields=['report_pdf_url'])
    logger.info("PDF report saved locally for application #%s at %s", app.id, file_path)
    return relative_url
