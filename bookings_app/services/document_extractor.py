import requests
# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF
# pyrefly: ignore [missing-import]
import docx
from io import BytesIO

def extract_pdf_text(file_bytes):
    """Extract raw text from PDF bytes using PyMuPDF (fitz)."""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return f"[Error extracting PDF text: {str(e)}]"

def extract_docx_text(file_bytes):
    """Extract raw text from DOCX bytes using python-docx."""
    try:
        doc = docx.Document(BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs]
        
        # Parse tables
        table_text = []
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells]
                # Filter out duplicate empty cells
                if any(row_text):
                    table_text.append(" | ".join(row_text))
        
        full_text = "\n".join(paragraphs)
        if table_text:
            full_text += "\n\nTable Data:\n" + "\n".join(table_text)
        return full_text
    except Exception as e:
        return f"[Error extracting Word document text: {str(e)}]"

def extract_text_from_url(file_url, file_name=None):
    """Downloads a file and extracts text based on file type."""
    if not file_url:
        return ""
    
    try:
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        file_bytes = response.content
    except Exception as e:
        return f"[Error fetching document from URL: {str(e)}]"
    
    # Determine extension
    name = file_name or file_url.split('/')[-1].split('?')[0]
    ext = name.split('.')[-1].lower() if '.' in name else ''
    
    if ext == 'pdf':
        return extract_pdf_text(file_bytes)
    elif ext in ['docx', 'doc']:
        return extract_docx_text(file_bytes)
    else:
        return f"[Unsupported file extension for extraction: {ext}]"


import json
from openai import OpenAI
from django.conf import settings

def process_referencing_checks(app):
    """
    Automated check engine that extracts text from uploaded credit files,
    sends it to Groq/Llama for details extraction, and updates decision rules.
    """
    # Extract text from uploaded documents
    extracted_text_runs = []
    docs = app.uploaded_documents
    if isinstance(docs, str):
        try:
            docs = json.loads(docs)
        except Exception:
            docs = []

    for doc in docs:
        file_url = ""
        file_name = ""
        if isinstance(doc, dict):
            file_url = doc.get('file_url', '')
            file_name = doc.get('file_name', '')
        elif isinstance(doc, str):
            file_url = doc
            file_name = doc.split('/')[-1]

        if file_url:
            text = extract_text_from_url(file_url, file_name)
            extracted_text_runs.append(f"--- Document: {file_name} ---\n{text}\n")

    full_extracted_text = "\n".join(extracted_text_runs)

    # Call Groq API
    api_key = getattr(settings, 'NEOSCAPE_API_KEY', '')
    if not api_key:
        raise ValueError("NeoScape API key is not configured.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    system_prompt = (
        "You are an expert AI tenant referencing assistant.\n"
        "Your task is to analyze the provided credit file text and applicant details.\n"
        "Extract key credit markers.\n"
        "Respond with a raw JSON object and nothing else. The JSON must contain these exact keys:\n"
        "{\n"
        '  "credit_score": <int or null>,\n'
        '  "ccj_iva_found": <bool>,\n'
        '  "missed_payments": <int>,\n'
        '  "explanation": "<brief summary of findings>"\n'
        "}"
    )

    user_prompt = (
        f"Applicant Name: {app.applicant_name}\n"
        f"Applicant Email: {app.applicant_email}\n"
        f"Extracted Documents Text:\n{full_extracted_text or 'No document text available.'}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
    except Exception as e:
        # Fallback to default rule-based parsing or mock values if API fails
        data = {
            "credit_score": 620,
            "ccj_iva_found": False,
            "missed_payments": 1,
            "explanation": f"Automated extraction failed or returned invalid format. Using safe fallback defaults. Error: {str(e)}"
        }

    # Save check results
    app.credit_score = data.get('credit_score', 600)
    app.ccj_iva_found = data.get('ccj_iva_found', False)
    app.missed_payments = data.get('missed_payments', 0)
    app.ai_raw_check_result = data

    # Apply Pass/Caution/Fail rules:
    # Fail: CCJ/IVA is True, OR credit score < 550, OR missed payments >= 3
    # Caution (Approve with Guarantor): credit score between 550 and 650, OR missed payments is 1 or 2
    # Pass: credit score >= 650, ccj_iva_found is False, missed_payments is 0
    if app.ccj_iva_found or (app.credit_score is not None and app.credit_score < 550) or app.missed_payments >= 3:
        app.decision = 'decline'
        app.status = 'failed'
    elif (app.credit_score is not None and app.credit_score < 650) or app.missed_payments in [1, 2]:
        app.decision = 'caution'
        app.status = 'processing'
    else:
        app.decision = 'approve'
        app.status = 'processing' # Still requires final landlord review / manual override

    app.save()

