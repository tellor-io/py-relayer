import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

sender_username=os.getenv("EMAIL_USERNAME")
sender_email=f"{sender_username}@gmail.com"
recipients=os.getenv("EMAIL_RECIPIENTS").split(",")
password=os.getenv("EMAIL_PASSWORD")

def send_email_alert(subject, message) -> Exception:
    try:
        send_email(subject, message, sender_username, sender_email, recipients, password)
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

