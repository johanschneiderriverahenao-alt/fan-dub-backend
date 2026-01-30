"""
Email service for sending verification codes via Resend.
"""
# pylint: disable=W0718,C0301

import random
import resend
from app.config.settings import settings
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)

resend.api_key = settings.resend_api_key


class EmailService:
    """Service for sending verification emails."""

    @staticmethod
    def generate_verification_code() -> str:
        """
        Generate a 6-digit verification code.

        Returns:
            Six-digit code as string.
        """
        return str(random.randint(100000, 999999))

    @staticmethod
    def _get_verification_email_html(code: str, purpose: str = "registration") -> str:
        """
        Generate HTML template for verification email.

        Args:
            code: 6-digit verification code.
            purpose: Purpose of the code (registration or password_change).

        Returns:
            HTML string for email body.
        """
        if purpose == "registration":
            title = "Confirma tu cuenta"
            message = (
                "Gracias por registrarte en YouDub. "
                "Usa el siguiente código para confirmar tu cuenta:"
            )

        else:
            title = "Cambia tu contraseña"
            message = (
                "Has solicitado cambiar tu contraseña. "
                "Usa el siguiente código para continuar:"
            )

        html = f"""
        <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;background:#0f172a;color:#e5e7eb;border-radius:12px;overflow:hidden">
            <div style="padding:24px;background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);text-align:center">
                <h1 style="margin:0;color:#ffffff;font-size:28px">🎙️ YouDub</h1>
                <p style="margin:8px 0 0;color:#e0e7ff;font-size:14px">Doblajes interactivos</p>
            </div>

            <div style="padding:32px">
                <h2 style="color:#38bdf8;margin:0 0 16px 0">{title}</h2>
                <p style="line-height:1.6;margin:0 0 24px 0">{message}</p>

                <div style="margin:24px 0;padding:20px;text-align:center;background:#020617;border-radius:8px;border:2px solid #38bdf8">
                    <span style="font-size:32px;letter-spacing:8px;font-weight:bold;color:#38bdf8">{code}</span>
                </div>

                <p style="font-size:14px;color:#94a3b8;margin:24px 0 0 0">
                    ⏱️ Este código expira en 10 minutos.
                </p>

                <p style="font-size:13px;color:#64748b;margin:16px 0 0 0;padding-top:16px;border-top:1px solid #1e293b">
                    Si no solicitaste esto, puedes ignorar este correo de forma segura.
                </p>
            </div>

            <div style="padding:20px;background:#020617;text-align:center">
                <p style="margin:0;font-size:12px;color:#64748b">
                    © 2026 YouDub
                </p>
                <p style="margin:8px 0 0 0;font-size:11px;color:#475569">
                    Enviado por <span style="color:#38bdf8">RH Studios</span>
                </p>
            </div>
        </div>
        """  # noqa: E501
        return html

    @staticmethod
    async def send_verification_email(
        email: str,
        code: str,
        purpose: str = "registration"
    ) -> bool:
        """
        Send verification code email using Resend.

        Args:
            email: Recipient email address.
            code: 6-digit verification code.
            purpose: Purpose of verification (registration or password_change).

        Returns:
            True if email sent successfully, False otherwise.
        """
        try:
            subject = (
                "🎬 Bienvenido a YouDub — Confirma tu cuenta"
                if purpose == "registration"
                else "🔒 YouDub — Confirma el cambio de contraseña"
            )

            html_content = EmailService._get_verification_email_html(code, purpose)

            params = {
                "from": settings.resend_from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)

            log_info(
                logger,
                f"Verification email sent successfully to {email}",
                {"response_id": response.get("id"), "purpose": purpose}
            )
            return True

        except Exception as e:
            log_error(
                logger,
                f"Failed to send verification email to {email}",
                {"error": str(e), "purpose": purpose}
            )
            return False
