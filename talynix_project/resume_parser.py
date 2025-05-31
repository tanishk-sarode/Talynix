# Resume parsing module

import os
import re
import json
import logging
from typing import Dict, Any

import spacy
from spacy.matcher import Matcher
from collections import defaultdict

try:
    import docx
except ImportError:
    docx = None
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

# Load spaCy model (English)
try:
    nlp = spacy.load('en_core_web_sm')
except Exception:
    nlp = None

# Ensure log directory exists before configuring logging
os.makedirs(os.path.dirname('talynix_project/talynix.log'), exist_ok=True)
logging.basicConfig(filename='talynix_project/talynix.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

def extract_text_from_pdf(file_path: str) -> str:
    if not PdfReader:
        raise ImportError('PyPDF2 is not installed.')
    try:
        reader = PdfReader(file_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text() or ''
        return text
    except Exception as e:
        logging.error(f'PDF parsing failed: {e}')
        raise

def extract_text_from_docx(file_path: str) -> str:
    if not docx:
        raise ImportError('python-docx is not installed.')
    try:
        doc = docx.Document(file_path)
        return '\n'.join([para.text for para in doc.paragraphs])
    except Exception as e:
        logging.error(f'DOCX parsing failed: {e}')
        raise

def clean_text(text: str) -> str:
    # Remove common icon unicodes and extra whitespace
    icon_patterns = [
        r'[\u2600-\u26FF]',  # Misc symbols
        r'[\u2700-\u27BF]',  # Dingbats
        r'[\uE000-\uF8FF]',  # Private Use Area
        r'[\u2190-\u21FF]',  # Arrows
        r'[\u2300-\u23FF]',  # Misc technical
        r'[\u25A0-\u25FF]',  # Geometric shapes
        r'[\u1F300-\u1F5FF]', # Misc symbols and pictographs
        r'[\u1F600-\u1F64F]', # Emoticons
        r'[\u1F680-\u1F6FF]', # Transport and map
        r'[\u1F700-\u1F77F]', # Alchemical symbols
        r'[\u1F780-\u1F7FF]', # Geometric Extended
        r'[\u1F800-\u1F8FF]', # Supplemental Arrows-C
        r'[\u1F900-\u1F9FF]', # Supplemental Symbols and Pictographs
        r'[\u1FA00-\u1FA6F]', # Chess Symbols
        r'[\u1FA70-\u1FAFF]', # Symbols and Pictographs Extended-A
    ]
    for pat in icon_patterns:
        text = re.sub(pat, '', text)
    # Remove stray slashes and extra whitespace
    text = re.sub(r'[\u200b\u200c\u200d\uFEFF]', '', text)  # zero-width
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def extract_email(text: str) -> str:
    # Find the line with '@' and clean icons only there
    for line in text.split('\n'):
        if '@' in line:
            cleaned = re.sub(r'[\u2600-\u26FF\u2700-\u27BF\uE000-\uF8FF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u1F300-\u1F5FF\u1F600-\u1F64F\u1F680-\u1F6FF\u1F700-\u1F77F\u1F780-\u1F7FF\u1F800-\u1F8FF\u1F900-\u1F9FF\u1FA00-\u1FA6F\u1FA70-\u1FAFF]', '', line)
            match = re.search(r'[\w\.-]+@[\w\.-]+', cleaned)
            if match:
                return match.group(0)
    # fallback
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else ''

def extract_phone(text: str) -> str:
    # Find the line with phone-like numbers and clean icons only there
    for line in text.split('\n'):
        if re.search(r'\+?\d[\d\s\-\(\)]{8,}\d', line):
            cleaned = re.sub(r'[\u2600-\u26FF\u2700-\u27BF\uE000-\uF8FF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u1F300-\u1F5FF\u1F600-\u1F64F\u1F680-\u1F6FF\u1F700-\u1F77F\u1F780-\u1F7FF\u1F800-\u1F8FF\u1F900-\u1F9FF\u1FA00-\u1FA6F\u1FA70-\u1FAFF]', '', line)
            match = re.search(r'(\+?\d[\d\s\-\(\)]{8,}\d)', cleaned)
            if match:
                return match.group(0).replace(' ', '').replace('-', '')
    # fallback
    match = re.search(r'(\+?\d[\d\s\-\(\)]{8,}\d)', text)
    return match.group(0).replace(' ', '').replace('-', '') if match else ''

def extract_name(text: str) -> str:
    if not nlp:
        return ''
    doc = nlp(text[:500])
    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            return ent.text
    # fallback: first line
    return text.split('\n')[0].strip()

def extract_section(text: str, section_names, all_section_names=None) -> str:
    # Improved: Find section by header, stop at the next section header
    if all_section_names is None:
        all_section_names = [
            "Education", "Academic Background", "Work Experience", "Experience", "Professional Experience",
            "Projects", "Academic Projects", "Technical Skills", "Key Skills", "Skills",
            "Certifications", "Certificates", "Extracurricular Activities"
        ]
    pattern = r'|'.join([re.escape(name) for name in section_names])
    all_headers = r'|'.join([re.escape(name) for name in all_section_names])
    match = re.search(rf'({pattern})[:\s\n]+', text, re.IGNORECASE)
    if not match:
        return ''
    start = match.end()
    # Find the next section header after this one
    next_match = re.search(rf'\n({all_headers})[:\s\n]+', text[start:], re.IGNORECASE)
    end = start + next_match.start() if next_match else len(text)
    section_text = text[start:end].strip()
    return section_text

def extract_skills(text: str) -> list:
    section = extract_section(text, ['Skills', 'Technical Skills', 'Key Skills'])
    if section:
        # Split by comma or newline
        skills = re.split(r',|\n', section)
        return [s.strip() for s in skills if s.strip()]
    # fallback: NER
    if nlp:
        doc = nlp(text)
        matcher = Matcher(nlp.vocab)
        patterns = [[{'POS': 'NOUN'}], [{'POS': 'PROPN'}]]
        matcher.add('SKILL', patterns)
        matches = matcher(doc)
        return list(set([doc[start:end].text for match_id, start, end in matches]))
    return []

def extract_education(text: str) -> list:
    section = extract_section(text, ['Education', 'Academic Background'])
    if section:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        return lines
    return []

def extract_experience(text: str) -> list:
    section = extract_section(text, ['Experience', 'Work Experience', 'Professional Experience'])
    if section:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        return lines
    return []

def extract_projects(text: str) -> list:
    section = extract_section(text, ['Projects', 'Academic Projects'])
    if section:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        return lines
    return []

def extract_certifications(text: str) -> list:
    section = extract_section(text, ['Certifications', 'Certificates'])
    if section:
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        return lines
    return []

def parse_resume(file_path: str) -> Dict[str, Any]:
    ext = os.path.splitext(file_path)[-1].lower()
    try:
        if ext == '.pdf':
            text = extract_text_from_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            text = extract_text_from_docx(file_path)
        else:
            raise ValueError('Unsupported file type')
    except Exception as e:
        logging.error(f'Failed to extract text: {e}')
        raise
    # Do NOT globally clean text here!
    data = {
        'name': extract_name(text),
        'email': extract_email(text),
        'phone': extract_phone(text),
        'education': extract_education(text),
        'experience': extract_experience(text),
        'skills': extract_skills(text),
        'projects': extract_projects(text),
        'certifications': extract_certifications(text),
        'raw_text': text[:1000]  # for debugging/preview
    }
    # Save to storage
    try:
        with open('talynix_project/storage/resume_data.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.warning(f'Could not save resume data: {e}')
    return data

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        result = parse_resume(sys.argv[1])
        print(json.dumps(result, indent=2))
