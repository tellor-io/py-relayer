import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

SENDER_USERNAME=os.getenv("EMAIL_USERNAME")
SENDER_EMAIL=f"{SENDER_USERNAME}@gmail.com"
RECIPIENTS=os.getenv("EMAIL_RECIPIENTS").split(",")
PASSWORD=os.getenv("EMAIL_PASSWORD")

def send_email_alert(subject, message) -> Exception:
    try:
        send_email(subject, message, SENDER_USERNAME, SENDER_EMAIL, RECIPIENTS, PASSWORD)
    except Exception as e:
        print(f"Error sending email: {e}")
        return e
    return None

def send_email(subject, body, sender_username, sender_email, recipients, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender_username, password)
       smtp_server.sendmail(sender_email, recipients, msg.as_string())
    print("Message sent!")

