import logging
from pathlib import Path
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from typing import Optional

import aiosmtplib
from aiosmtplib import SMTPAuthenticationError, SMTPConnectError, SMTPException

logger = logging.getLogger(__name__)

class EmailSendingError(Exception):
    """Custom exception raised when email sending fails."""
    pass

class AsyncEmailSender:
    """
    An asynchronous SMTP email client for sending job applications.
    
    IMPORTANT: Users with Gmail, Microsoft, or similar accounts with 2FA enabled
    must use "App Passwords" instead of their standard account passwords.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender_email: str
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender_email = sender_email

    async def send_application(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cv_pdf_path: Optional[str] = None
    ) -> None:
        """
        Constructs and sends a MIME email with a plain text body and an optional PDF CV attachment.
        """
        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        # Using domain from sender_email to help with spam filters
        domain = self.sender_email.split('@')[-1] if '@' in self.sender_email else "localhost"
        msg["Message-ID"] = make_msgid(domain=domain)
        
        # Set plain text body (UTF-8)
        msg.set_content(body, charset="utf-8")

        # Attach PDF if provided
        if cv_pdf_path:
            cv_path = Path(cv_pdf_path)
            if not cv_path.is_file():
                error_msg = f"CV file not found at path: {cv_pdf_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            cv_bytes = cv_path.read_bytes()
            msg.add_attachment(
                cv_bytes,
                maintype="application",
                subtype="pdf",
                filename=cv_path.name
            )

        # Intelligent connection logic
        use_tls = self.port == 465
        start_tls = self.port == 587 or (not use_tls and self.port != 25)

        logger.info(f"Connecting to SMTP server {self.host}:{self.port} to send email to {recipient_email}")
        try:
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                use_tls=use_tls,
                start_tls=start_tls,
            ) as server:
                await server.login(self.username, self.password)
                await server.send_message(msg)
                
            logger.info(f"Email successfully sent to {recipient_email}")

        except SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}. Check credentials or App Password settings.")
            raise EmailSendingError(f"Authentication failed: {e}") from e
        except SMTPConnectError as e:
            logger.error(f"Failed to connect to SMTP server {self.host}:{self.port}: {e}")
            raise EmailSendingError(f"Connection failed: {e}") from e
        except SMTPException as e:
            logger.error(f"SMTP error occurred while sending email to {recipient_email}: {e}")
            raise EmailSendingError(f"SMTP error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error while sending email: {e}")
            raise EmailSendingError(f"Unexpected error: {e}") from e
