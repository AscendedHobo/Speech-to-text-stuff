import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib import utils


def md_to_paragraphs(md_text):
    # Extremely simple MD to paragraphs (headings bolded, lists kept as text)
    # Keeps it readable without external tools.
    styles = getSampleStyleSheet()
    normal = styles['BodyText']
    normal.fontName = 'Helvetica'
    normal.fontSize = 11
    normal.leading = 14
    title = styles['Heading1']
    h2 = styles['Heading2']
    h3 = styles['Heading3']

    flow = []
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 0.15 * inch))
            continue
        if line.startswith('# '):
            flow.append(Paragraph(line[2:].strip(), title))
        elif line.startswith('## '):
            flow.append(Paragraph(line[3:].strip(), h2))
        elif line.startswith('### '):
            flow.append(Paragraph(line[4:].strip(), h3))
        else:
            # Escape angle brackets lightly
            safe = line.replace('<', '&lt;').replace('>', '&gt;')
            flow.append(Paragraph(safe, normal))
    return flow


def build_pdf(md_path, pdf_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Whisper Transcriber – User Guide",
        author="Whisper Transcriber",
    )
    story = md_to_paragraphs(md_text)
    doc.build(story)


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    md = os.path.join(here, 'docs', 'user_guide.md')
    pdf = os.path.join(here, 'docs', 'Whisper_Transcriber_User_Guide.pdf')
    if not os.path.isfile(md):
        raise FileNotFoundError(md)
    os.makedirs(os.path.dirname(pdf), exist_ok=True)
    build_pdf(md, pdf)
    print(f"Built guide: {pdf}")


if __name__ == '__main__':
    main()

