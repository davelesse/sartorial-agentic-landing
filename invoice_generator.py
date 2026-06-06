#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generateur de factures PDF -- Digital Colosse LLC (Wyoming, USA)
TVA : 0% -- Services rendered by a US entity
"""
import os
from datetime import datetime
from io import BytesIO


def generate_invoice_pdf(invoice_number, invoice_date, customer_name,
                         customer_email, customer_address="",
                         customer_country="", plan_label="",
                         amount=0.0, currency="EUR"):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import mm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                        Spacer, Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    except ImportError:
        raise ImportError("pip3 install reportlab")

    GOLD=HexColor("#D4AF37"); TEAL=HexColor("#48D1CC"); BLACK=HexColor("#000000")
    DARK=HexColor("#0f0f0f"); SURFACE=HexColor("#1a1a1a"); BORDER=HexColor("#2a2a2a")
    WHITE=HexColor("#ffffff"); MUTED=HexColor("#666666")

    sym = "€" if currency == "EUR" else ("$" if currency == "USD" else currency)
    def fmt(v): return f"{v:,.2f} {sym}".replace(",", " ")
    def ps(name, size=10, color=WHITE, font="Helvetica",
           align=TA_LEFT, leading=16, spacing=0):
        return ParagraphStyle(name, fontSize=size, textColor=color, fontName=font,
                              alignment=align, leading=leading, letterSpacing=spacing)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    story = []

    # HEADER
    hd = Table([
        [Paragraph("<b>DIGITAL COLOSSE</b>", ps("dc",20,GOLD,"Helvetica-Bold")),
         Paragraph("INVOICE", ps("inv",32,WHITE,"Helvetica-Bold",TA_RIGHT))],
        [Paragraph("Solar Intelligence", ps("tag",9,TEAL,spacing=1)),
         Paragraph("No. <b>" + invoice_number + "</b>", ps("num",11,GOLD,align=TA_RIGHT))],
    ], colWidths=[90*mm, 80*mm])
    hd.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),DARK),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(0,-1),8),("RIGHTPADDING",(-1,0),(-1,-1),8),
    ]))
    story.append(hd)
    story.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=12))

    # PARTIES
    issuer = ("<b>Digital Colosse LLC</b><br/>30 N Gould St Ste R<br/>"
              "Sheridan, WY 82801 — USA<br/>EIN: 00-0000000<br/>"
              "contact@digital-colosse.com")
    client_txt = "<b>" + customer_name + "</b><br/>" + customer_email
    if customer_address: client_txt += "<br/>" + customer_address
    if customer_country: client_txt += "<br/>" + customer_country

    pt = Table([
        [Paragraph(issuer, ps("em",9,MUTED,leading=14)),
         Paragraph("BILL TO", ps("bt",8,TEAL,font="Helvetica-Bold",spacing=2))],
        ["", Paragraph(client_txt, ps("cl",9,WHITE,leading=14))],
    ], colWidths=[85*mm, 85*mm])
    pt.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(1,0),(1,-1),20),
    ]))
    story.append(pt)

    mt = Table([
        [Paragraph("Date: <b>" + invoice_date + "</b>", ps("dt",9,MUTED,leading=14)),
         Paragraph("<b>PAID</b>", ps("paid",10,TEAL,font="Helvetica-Bold",align=TA_RIGHT))],
    ], colWidths=[85*mm, 85*mm])
    mt.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(mt)
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=16))

    # LIGNES
    hrow = [
        Paragraph("DESCRIPTION", ps("lh",8,TEAL,font="Helvetica-Bold",spacing=2)),
        Paragraph("QTY", ps("lh2",8,TEAL,font="Helvetica-Bold",align=TA_CENTER,spacing=2)),
        Paragraph("UNIT", ps("lh3",8,TEAL,font="Helvetica-Bold",align=TA_RIGHT,spacing=2)),
        Paragraph("TOTAL", ps("lh4",8,TEAL,font="Helvetica-Bold",align=TA_RIGHT,spacing=2)),
    ]
    desc = ("Digital Colosse Subscription — <b>" + plan_label
            + "</b> Level — Oracle + Aurum Agents — Monthly access")
    drow = [
        Paragraph(desc, ps("lr",9,WHITE,leading=14)),
        Paragraph("1", ps("qty",9,WHITE,align=TA_CENTER)),
        Paragraph(fmt(amount), ps("unit",9,WHITE,align=TA_RIGHT)),
        Paragraph(fmt(amount), ps("tot",9,WHITE,align=TA_RIGHT)),
    ]
    lt = Table([hrow, drow], colWidths=[95*mm, 15*mm, 25*mm, 35*mm])
    lt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),SURFACE),("BACKGROUND",(0,1),(-1,1),DARK),
        ("LINEBELOW",(0,0),(-1,0),0.5,GOLD),("LINEBELOW",(0,1),(-1,1),0.5,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(0,-1),8),("RIGHTPADDING",(-1,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(lt)
    story.append(Spacer(1, 8*mm))

    # TOTAUX
    tot_rows = [
        ["", Paragraph("Subtotal", ps("st",10,MUTED)),
              Paragraph(fmt(amount), ps("stv",10,WHITE,align=TA_RIGHT))],
        ["", Paragraph("Tax / VAT", ps("tax",10,MUTED)),
              Paragraph("0.00 (exempt)", ps("taxv",10,MUTED,align=TA_RIGHT))],
        ["", Paragraph("<b>TOTAL DUE</b>", ps("ttc",12,GOLD,font="Helvetica-Bold")),
              Paragraph("<b>" + fmt(amount) + "</b>",
                        ps("ttcv",12,GOLD,font="Helvetica-Bold",align=TA_RIGHT))],
    ]
    tt = Table(tot_rows, colWidths=[85*mm, 50*mm, 35*mm])
    tt.setStyle(TableStyle([
        ("LINEABOVE",(1,2),(-1,2),1,GOLD),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(-1,0),(-1,-1),8),
    ]))
    story.append(tt)
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=BORDER, spaceBefore=12, spaceAfter=10))

    # FOOTER
    footer = ("Digital Colosse LLC — 30 N Gould St Ste R, Sheridan WY 82801, USA<br/>"
              "Services rendered by a US entity — Tax/VAT not applicable — "
              "Please retain for your records.")
    story.append(Paragraph(footer, ps("ft",8,MUTED,leading=13,align=TA_CENTER)))

    def black_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLACK)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=black_bg, onLaterPages=black_bg)
    return buf.getvalue()


def send_invoice_email(to_email, customer_name, plan_name, amount,
                       invoice_number=None, tenant_id="default",
                       customer_address="", customer_country="",
                       currency="EUR"):
    import smtplib, logging
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    logger = logging.getLogger("InvoiceGenerator")

    smtp_host     = os.getenv("SMTP_HOST","")
    smtp_port     = int(os.getenv("SMTP_PORT", 587))
    smtp_user     = os.getenv("SMTP_USER","")
    smtp_password = os.getenv("SMTP_PASSWORD","")
    from_email    = os.getenv("FROM_EMAIL", os.getenv("EMAIL_FROM", smtp_user))

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning("SMTP non configure"); return False

    if not invoice_number:
        now = datetime.now()
        invoice_number = "DC-" + now.strftime("%Y-%m") + "-" + now.strftime("%f")[:4]
    invoice_date = datetime.now().strftime("%d/%m/%Y")

    PLAN_DB = {
        "niveau essence":   "ESSENCE",
        "niveau éther":    "ÉTHER",
        "niveau paradise":  "PARADISE",
        "niveau souverain": "SOUVERAIN",
    }
    plan_label = PLAN_DB.get(plan_name.lower().strip(), plan_name.upper())
    sym = "€" if currency == "EUR" else "$"

    try:
        from email_templates import email_engine
        subject, html = email_engine.render(
            "invoice", tenant_id,
            customer_name=customer_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            plan_label=plan_label,
            amount=f"{amount:.2f} {sym}",
            amount_ht=f"{amount:.2f} {sym}",
            amount_tva="0.00 (exempt)",
        )
    except Exception as e:
        logger.error("Erreur template : " + str(e)); return False

    try:
        pdf_bytes = generate_invoice_pdf(
            invoice_number=invoice_number, invoice_date=invoice_date,
            customer_name=customer_name, customer_email=to_email,
            customer_address=customer_address, customer_country=customer_country,
            plan_label=plan_label, amount=amount, currency=currency,
        )
    except Exception as e:
        logger.error("Erreur PDF : " + str(e)); return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"]    = "Digital Colosse — Billing <" + from_email + ">"
        msg["To"]      = to_email
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)
        pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", "attachment",
                            filename=invoice_number + ".pdf")
        msg.attach(pdf_part)

        if smtp_port == 465:
            import ssl
            with smtplib.SMTP_SSL(smtp_host, smtp_port,
                                   context=ssl.create_default_context()) as s:
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.ehlo(); s.starttls()
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())

        logger.info("Facture " + invoice_number + " envoyee -> " + to_email)
        return True
    except Exception as e:
        logger.error("Erreur SMTP : " + str(e)); return False


if __name__ == "__main__":
    pdf = generate_invoice_pdf(
        invoice_number="DC-2026-001",
        invoice_date="05/06/2026",
        customer_name="Test Client",
        customer_email="contact@digital-colosse.com",
        customer_country="Belgium",
        plan_label="ESSENCE",
        amount=147.00,
        currency="EUR",
    )
    with open("/tmp/test_invoice.pdf", "wb") as f:
        f.write(pdf)
    print(f"PDF genere : /tmp/test_invoice.pdf ({len(pdf)} bytes)")
