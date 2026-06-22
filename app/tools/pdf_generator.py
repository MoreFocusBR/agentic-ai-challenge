import os
import uuid
import re
import unicodedata
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)

from app.config import settings


def generate_pdf(title: str, content: str) -> str:
    """
    Gera um PDF a partir de título e conteúdo estruturado.
    Retorna o nome do arquivo gerado (salvo em documents/).
    """
    os.makedirs(settings.documents_dir, exist_ok=True)

    normalized = unicodedata.normalize("NFKD", title.lower()).encode("ascii", "ignore").decode()
    safe = re.sub(r"[^\w\-]", "_", normalized)[:40]
    filename = f"{safe}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(settings.documents_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom", parent=styles["Title"],
        fontSize=20, textColor=HexColor("#1a3a5c"), spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "BodyCustom", parent=styles["Normal"],
        fontSize=11, leading=16, spaceAfter=10,
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"],
        fontSize=8, textColor=HexColor("#888888"),
    )

    elements = [
        Paragraph(title, title_style),
        HRFlowable(width="100%", color=HexColor("#1a3a5c"), thickness=1.5),
        Spacer(1, 0.4 * cm),
    ]

    for para in content.split("\n"):
        if para.strip():
            elements.append(Paragraph(para.strip(), body_style))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(HRFlowable(width="100%", color=HexColor("#cccccc"), thickness=0.5))
    elements.append(Paragraph(
        f"Documento gerado automaticamente em "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
        meta_style,
    ))

    doc.build(elements)
    return filename
