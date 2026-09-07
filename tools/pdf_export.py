"""Paginated PDF export using escaped text and a repeatable page footer."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

def build_pdf(plan):
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=48, leftMargin=48,
                            topMargin=56, bottomMargin=56, title=f"Voyagent. {plan['trip']['destination']}.", author='Voyagent')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TripTitle', fontName='Helvetica-Bold', fontSize=28, leading=32, spaceAfter=20, textColor=colors.HexColor('#141414')))
    styles.add(ParagraphStyle(name='TripBody', fontName='Helvetica', fontSize=10, leading=15, spaceAfter=10, textColor=colors.HexColor('#262626'), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='TripHeading', fontName='Helvetica-Bold', fontSize=16, leading=21, spaceBefore=16, spaceAfter=10, keepWithNext=True))
    story = []
    group = []
    parts = plan['answer'].split('\n\n')
    for index, value in enumerate(parts):
        # Standard PDF fonts cover our fixed English demo fixtures.
        safe = escape(value.encode('latin-1', 'replace').decode('latin-1'))
        heading = value in ('Flights.', 'Hotels.', 'Itinerary.', 'Budget.') or value.startswith('Day ')
        if heading and group:
            story.append(KeepTogether(group))
            group = []
        style = styles['TripTitle' if index == 0 else ('TripHeading' if heading else 'TripBody')]
        group.append(Paragraph(safe, style))
    if group:
        story.append(KeepTogether(group))
    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#e0e0e0'))
        canvas.line(48, 42, A4[0] - 48, 42)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#707070'))
        canvas.drawString(48, 28, 'VOYAGENT / ESTIMATED COSTS / NO BOOKINGS MADE')
        canvas.drawRightString(A4[0] - 48, 28, str(document.page))
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
