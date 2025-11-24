import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")


async def send_confirmation_email(to_email: str, user_name: str = "") -> bool:
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = "You're Subscribed to TruthLens Newsletter!"
        message["From"] = EMAIL_USER
        message["To"] = to_email

        html = f"""
        <html>
        <body>
            <h2 style="color:#ff5700;">Welcome to TruthLens 📰🔥</h2>
            <p>Hi <b>{user_name or "Subscriber"}</b>,</p>
            <p>Thanks for subscribing! You'll now receive updates and verified news insights.</p>

            <br>
            <p>Stay informed,<br><strong>TruthLens Team</strong></p>

            <hr style="margin-top:20px;">
            <small>This is an automated message — no reply needed.</small>
        </body>
        </html>
        """

        message.attach(MIMEText(html, "html"))

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, to_email, message.as_string())

        return True

    except Exception as e:
        print("Email sending failed →", e)
        return False
