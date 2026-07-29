"""
daily_schedule_email.py

Builds and sends the daily "who's being evaluated today" email — a printable
roster (HTML email body + PDF attachment) coaches can post on the wall.

Env vars required (set these in Railway / your deploy environment):
    SMTP_HOST                 default: smtp.gmail.com
    SMTP_PORT                 default: 587
    SMTP_USER                 your Gmail address, e.g. schedule@pwrx.com
    SMTP_PASSWORD             a 16-character Gmail App Password (NOT your normal
                               Gmail password — Google requires an App Password
                               for SMTP. Generate one at myaccount.google.com/apppasswords,
                               which requires 2-Step Verification to be turned on
                               for the account first)
    EMAIL_FROM                optional, defaults to SMTP_USER
    SCHEDULE_EMAIL_RECIPIENTS optional, comma-separated default recipient list

Manual test usage:
    python daily_schedule_email.py --date 2026-07-30 --to coach@pwrx.com

If --date is omitted, defaults to today. If --to is omitted, falls back to
SCHEDULE_EMAIL_RECIPIENTS.
"""

import argparse
import datetime as dt
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

from sc_db import get_schedule_day

WRX_ORANGE = "#f4750d"
DARK_NAVY  = "#0A1830"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)
DEFAULT_RECIPIENTS = os.environ.get("SCHEDULE_EMAIL_RECIPIENTS", "")


def _format_time(t: str) -> str:
    """'09:30:00' -> '9:30 AM'"""
    try:
        return dt.datetime.strptime(t[:5], "%H:%M").strftime("%-I:%M %p")
    except Exception:
        return t


def _format_date(d: dt.date) -> str:
    return d.strftime("%A, %B %-d, %Y")


# ─────────────────────────────────────────────────────────────────────────────
# HTML email body (printable straight from the inbox)
# ─────────────────────────────────────────────────────────────────────────────

def build_html(sessions: list[dict], for_date: dt.date) -> str:
    date_label = _format_date(for_date)

    if not sessions:
        rows_html = (
            '<tr><td colspan="4" style="padding:16px;text-align:center;'
            'color:#666;font-family:Arial,sans-serif;">'
            "No evaluations scheduled for this date.</td></tr>"
        )
    else:
        rows_html = ""
        for s in sessions:
            tag = "New" if s["match_status"] == "new" else "Existing"
            tag_color = WRX_ORANGE if s["match_status"] == "new" else "#2c7a4b"
            rows_html += f"""
            <tr>
                <td style="padding:10px 12px;border-bottom:1px solid #ddd;font-family:Arial,sans-serif;">{_format_time(s['scheduled_time'])}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #ddd;font-family:Arial,sans-serif;">{s['athlete_name']}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #ddd;font-family:Arial,sans-serif;color:{tag_color};font-weight:bold;">{tag}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #ddd;font-family:Arial,sans-serif;">{s.get('notes') or ''}</td>
            </tr>"""

    return f"""\
<html>
<body style="margin:0;padding:24px;background:#f4f4f4;">
  <div style="max-width:720px;margin:0 auto;background:#fff;border:1px solid #ddd;">
    <div style="background:{DARK_NAVY};padding:18px 24px;border-top:5px solid {WRX_ORANGE};">
      <h2 style="margin:0;color:#fff;font-family:Arial,sans-serif;">PWRX Evaluation Schedule</h2>
      <div style="color:#c9d6e3;font-family:Arial,sans-serif;font-size:14px;margin-top:4px;">{date_label}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:#f0f0f0;">
          <th style="text-align:left;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;color:#333;">Time</th>
          <th style="text-align:left;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;color:#333;">Athlete</th>
          <th style="text-align:left;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;color:#333;">Status</th>
          <th style="text-align:left;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;color:#333;">Notes</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div style="padding:14px 24px;font-family:Arial,sans-serif;font-size:11px;color:#999;">
      A printable PDF version of this schedule is attached — feel free to print and post it.
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# PDF attachment (letter size, built for print/posting)
# ─────────────────────────────────────────────────────────────────────────────

def build_pdf(sessions: list[dict], for_date: dt.date, out_path: str) -> str:
    doc = SimpleDocTemplate(
        out_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(
        f'<font color="{WRX_ORANGE}"><b>PWRX</b></font> Evaluation Schedule',
        styles["Title"],
    )
    subtitle = Paragraph(_format_date(for_date), styles["Heading2"])
    story += [title, subtitle, Spacer(1, 14)]

    if not sessions:
        story.append(Paragraph("No evaluations scheduled for this date.", styles["Normal"]))
    else:
        header = ["Time", "Athlete", "Status", "Notes"]
        table_data = [header]
        for s in sessions:
            tag = "New" if s["match_status"] == "new" else "Existing"
            table_data.append([
                _format_time(s["scheduled_time"]),
                s["athlete_name"],
                tag,
                s.get("notes") or "",
            ])

        table = Table(table_data, colWidths=[1.0 * inch, 2.3 * inch, 1.1 * inch, 2.6 * inch])
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK_NAVY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ])
        # color the Status column per row: orange for New, green for Existing
        for i, s in enumerate(sessions, start=1):
            color = colors.HexColor(WRX_ORANGE) if s["match_status"] == "new" else colors.HexColor("#2c7a4b")
            style.add("TEXTCOLOR", (2, i), (2, i), color)
            style.add("FONTNAME", (2, i), (2, i), "Helvetica-Bold")
        table.setStyle(style)
        story.append(table)

    doc.build(story)
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Send via Gmail SMTP
# ─────────────────────────────────────────────────────────────────────────────

def send_daily_schedule_email(for_date: dt.date = None, recipients: list[str] = None,
                               pdf_path: str = "/tmp/pwrx_schedule.pdf") -> dict:
    if for_date is None:
        for_date = dt.date.today()

    if recipients is None:
        recipients = [r.strip() for r in DEFAULT_RECIPIENTS.split(",") if r.strip()]

    if not recipients:
        raise ValueError("No recipients provided and SCHEDULE_EMAIL_RECIPIENTS is not set.")
    if not SMTP_USER or not SMTP_PASSWORD:
        raise ValueError("SMTP_USER / SMTP_PASSWORD are not set in the environment.")

    sessions = get_schedule_day(for_date)

    html = build_html(sessions, for_date)
    build_pdf(sessions, for_date, pdf_path)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"PWRX Evaluation Schedule — {_format_date(for_date)}"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(html, "html"))

    with open(pdf_path, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="pdf")
        attachment.add_header(
            "Content-Disposition", "attachment",
            filename=f"pwrx_schedule_{for_date.isoformat()}.pdf",
        )
        msg.attach(attachment)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, recipients, msg.as_string())

    return {"status": "sent", "date": for_date.isoformat(), "recipients": recipients,
            "session_count": len(sessions)}


# ─────────────────────────────────────────────────────────────────────────────
# Manual CLI for testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually send the daily evaluation schedule email.")
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    parser.add_argument("--to", help="Comma-separated recipient list, defaults to SCHEDULE_EMAIL_RECIPIENTS")
    args = parser.parse_args()

    target_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    to_list = [r.strip() for r in args.to.split(",")] if args.to else None

    result = send_daily_schedule_email(target_date, to_list)
    print(result)
