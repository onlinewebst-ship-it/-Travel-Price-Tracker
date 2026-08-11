"""Optional email alerts. Silently disabled unless SMTP_* env vars are set."""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


def email_alerts_enabled() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("ALERT_EMAIL_TO"))


def send_alert(subject: str, body: str) -> None:
    if not email_alerts_enabled():
        return

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    sender = os.environ.get("ALERT_EMAIL_FROM") or user
    recipient = os.environ["ALERT_EMAIL_TO"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(sender, [recipient], msg.as_string())
