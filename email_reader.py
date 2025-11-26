import email
import imaplib
import re
import time
from email.header import decode_header

from config import EMAIL, IMAP_PORT, IMAP_SERVER


def get_otp_from_email(password, max_wait=120, check_interval=5):
    """
    Automatically retrieve OTP from email
    You need to enable IMAP in Gmail and use an App Password
    """
    try:
        # Connect to the IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)

        # Login
        mail.login(EMAIL, password)
        mail.select("inbox")

        print("Waiting for OTP email...")

        start_time = time.time()
        while time.time() - start_time < max_wait:
            # Search for unread emails from caworkcompcoverage@wcirb.com
            status, messages = mail.search(
                None, "UNSEEN", 'FROM "caworkcompcoverage@wcirb.com"'
            )

            if status == "OK" and messages[0]:
                email_ids = messages[0].split()

                # Get the latest email
                latest_email_id = email_ids[-1]

                # Fetch the email
                status, msg_data = mail.fetch(latest_email_id, "(RFC822)")

                if status == "OK":
                    # Parse email content
                    msg = email.message_from_bytes(msg_data[0][1])

                    # Get email body
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(
                                part.get("Content-Disposition")
                            )

                            if (
                                content_type == "text/plain"
                                and "attachment" not in content_disposition
                            ):
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()

                    # Extract OTP using regex (looking for 6-digit code)
                    otp_match = re.search(r"\b\d{6}\b", body)
                    if otp_match:
                        otp = otp_match.group(0)
                        print(f"Found OTP: {otp}")

                        # Mark as read (optional)
                        mail.store(latest_email_id, "+FLAGS", "\\Seen")

                        mail.logout()
                        return otp

            time.sleep(check_interval)

        mail.logout()
        print("Timeout waiting for OTP email")
        return None

    except Exception as e:
        print(f"Error reading email: {e}")
        return None


# Alternative simpler version that just looks for the pattern in subject/body
def get_otp_simple(password):
    """Simpler version that checks once"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL, password)
        mail.select("inbox")

        # Search for emails from the WCIRB
        status, messages = mail.search(
            None, 'FROM "caworkcompcoverage@wcirb.com"'
        )

        if status == "OK" and messages[0]:
            email_ids = messages[0].split()

            # Get the most recent email
            latest_email_id = email_ids[-1]
            status, msg_data = mail.fetch(latest_email_id, "(RFC822)")

            if status == "OK":
                msg = email.message_from_bytes(msg_data[0][1])

                # Try to get OTP from subject first
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()

                # Look for 6-digit code in subject
                otp_match = re.search(r"\b\d{6}\b", subject)
                if otp_match:
                    mail.logout()
                    return otp_match.group(0)

                # If not in subject, check body
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            otp_match = re.search(r"\b\d{6}\b", body)
                            if otp_match:
                                mail.logout()
                                return otp_match.group(0)

        mail.logout()
        return None

    except Exception as e:
        print(f"Error: {e}")
        return None
