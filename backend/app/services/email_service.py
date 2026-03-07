"""Email service for sending transactional emails via SendGrid."""

import logging
from typing import Optional, List
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SendGrid."""
    
    def __init__(self):
        """Initialize SendGrid client."""
        if not settings.sendgrid_api_key:
            logger.warning("SendGrid API key not configured. Email sending will fail.")
        self.client = SendGridAPIClient(settings.sendgrid_api_key) if settings.sendgrid_api_key else None
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """
        Send an email via SendGrid.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: Email body (HTML)
            text_content: Email body (plain text, optional)
            from_email: Sender email (defaults to settings.from_email)
            from_name: Sender name (defaults to settings.from_name)
            cc: List of CC email addresses
            bcc: List of BCC email addresses
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.client:
            logger.error("SendGrid client not initialized. Cannot send email to %s", to_email)
            return False
        
        try:
            from_email = from_email or settings.from_email
            from_name = from_name or settings.from_name
            
            # Create mail message
            message = Mail(
                from_email=Email(from_email, from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=text_content or "",
                html_content=html_content,
            )
            
            # Add CC recipients if provided
            if cc:
                for cc_email in cc:
                    message.add_cc(cc_email)
            
            # Add BCC recipients if provided
            if bcc:
                for bcc_email in bcc:
                    message.add_bcc(bcc_email)
            
            # Send email
            response = self.client.send(message)
            
            if response.status_code in (200, 201, 202):
                logger.info("Email sent successfully to %s (subject: %s)", to_email, subject)
                return True
            else:
                logger.error("Failed to send email to %s. Status: %s, Body: %s", 
                           to_email, response.status_code, response.body)
                return False
                
        except Exception as e:
            logger.error("Error sending email to %s: %s", to_email, str(e))
            return False
    
    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """
        Send a password reset email.
        
        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            
        Returns:
            True if sent successfully, False otherwise
        """
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Reset Your Password</h2>
                <p>You requested a password reset for your Sarson CRM account.</p>
                <p>Click the link below to reset your password:</p>
                <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">Reset Password</a></p>
                <p>Or copy this link: <a href="{reset_url}">{reset_url}</a></p>
                <p>This link will expire in {settings.password_reset_token_expire_hours} hours.</p>
                <p>If you didn't request this, please ignore this email.</p>
            </body>
        </html>
        """
        
        text_content = f"""
        Reset Your Password
        
        You requested a password reset for your Sarson CRM account.
        
        Click the link below to reset your password:
        {reset_url}
        
        This link will expire in {settings.password_reset_token_expire_hours} hours.
        
        If you didn't request this, please ignore this email.
        """
        
        return self.send_email(
            to_email=to_email,
            subject="Reset Your Sarson CRM Password",
            html_content=html_content,
            text_content=text_content,
        )
    
    def send_email_verification_email(self, to_email: str, verification_token: str) -> bool:
        """
        Send an email verification email.
        
        Args:
            to_email: Recipient email address
            verification_token: Email verification token
            
        Returns:
            True if sent successfully, False otherwise
        """
        verify_url = f"{settings.frontend_url}/verify-email?token={verification_token}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Verify Your Email</h2>
                <p>Welcome to Sarson CRM! Please verify your email address to complete your registration.</p>
                <p>Click the link below to verify your email:</p>
                <p><a href="{verify_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">Verify Email</a></p>
                <p>Or copy this link: <a href="{verify_url}">{verify_url}</a></p>
                <p>This link will expire in {settings.email_verification_token_expire_hours} hours.</p>
                <p>If you didn't create this account, please ignore this email.</p>
            </body>
        </html>
        """
        
        text_content = f"""
        Verify Your Email
        
        Welcome to Sarson CRM! Please verify your email address to complete your registration.
        
        Click the link below to verify your email:
        {verify_url}
        
        This link will expire in {settings.email_verification_token_expire_hours} hours.
        
        If you didn't create this account, please ignore this email.
        """
        
        return self.send_email(
            to_email=to_email,
            subject="Verify Your Sarson CRM Email",
            html_content=html_content,
            text_content=text_content,
        )


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
