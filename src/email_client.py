import smtplib
from email.mime.text import MIMEText
import os
from src.logger_utils import get_logger

logger = get_logger(__name__)

def send_email_alert(subject, message) -> Exception:
    try:
        send_email(subject, message, os.getenv("EMAIL_USERNAME"), os.getenv("EMAIL_RECIPIENTS"), os.getenv("EMAIL_PASSWORD"))
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return e
    return None

def send_email(subject, body, sender_username, recipients, password):
    sender_email = f"{sender_username}@gmail.com"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender_username, password)
       smtp_server.sendmail(sender_email, recipients, msg.as_string())
    logger.info("Message sent!")

