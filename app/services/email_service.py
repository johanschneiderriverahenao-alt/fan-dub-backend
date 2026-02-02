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

    @staticmethod
    def _get_first_dubbing_email_html(video_url: str) -> str:
        """
        Generate HTML template for first dubbing congratulations email.

        Args:
            video_url: URL of the dubbed video/audio.

        Returns:
            HTML string for email body.
        """
        html = f"""
        <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;background:#0f172a;color:#e5e7eb;border-radius:12px;overflow:hidden">
            <div style="padding:24px;background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);text-align:center">
                <h1 style="margin:0;color:#ffffff;font-size:28px">🎙️ YouDub</h1>
                <p style="margin:8px 0 0;color:#e0e7ff;font-size:14px">Doblajes interactivos</p>
            </div>

            <div style="padding:32px">
                <h2 style="color:#38bdf8;margin:0 0 16px 0">🎉 ¡Felicidades por tu primer doblaje!</h2>
                <p style="line-height:1.6;margin:0 0 24px 0;font-size:16px">
                    Has dado el primer paso en tu aventura como actor de doblaje. ¡Estamos emocionados de tenerte en YouDub! 🌟
                </p>

                <p style="line-height:1.6;margin:0 0 16px 0">
                    Tu doblaje está listo y puedes verlo/escucharlo aquí:
                </p>

                <div style="margin:24px 0;padding:20px;text-align:center;background:#020617;border-radius:8px;border:2px solid #10b981">
                    <a href="{video_url}" style="display:inline-block;padding:12px 32px;background:linear-gradient(135deg, #10b981 0%, #059669 100%);color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;font-size:16px">
                        ▶️ Ver mi doblaje
                    </a>
                </div>

                <div style="margin:24px 0;padding:16px;background:#1e293b;border-left:4px solid #38bdf8;border-radius:4px">
                    <p style="margin:0;font-size:14px;color:#94a3b8">
                        💡 <strong style="color:#38bdf8">Tip:</strong> Comparte tu doblaje con amigos y familia. ¡Seguro les encantará!
                    </p>
                </div>

                <p style="font-size:14px;color:#94a3b8;margin:24px 0 0 0;line-height:1.6">
                    Continúa creando más doblajes y mejorando tus habilidades. La práctica hace al maestro. 🎬
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
    async def send_first_dubbing_email(
        email: str,
        video_url: str
    ) -> bool:
        """
        Send congratulations email for first dubbing.

        Args:
            email: Recipient email address.
            video_url: URL of the dubbed video/audio.

        Returns:
            True if email sent successfully, False otherwise.
        """
        try:
            subject = "🎉 ¡Felicidades por tu primer doblaje en YouDub!"

            html_content = EmailService._get_first_dubbing_email_html(video_url)

            params = {
                "from": settings.resend_from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)

            log_info(
                logger,
                f"First dubbing congratulations email sent to {email}",
                {"response_id": response.get("id"), "video_url": video_url}
            )
            return True

        except Exception as e:
            log_error(
                logger,
                f"Failed to send first dubbing email to {email}",
                {"error": str(e)}
            )
            return False

    @staticmethod
    def _get_payment_success_email_html(plan_name: str, num_credits: int, features: list) -> str:
        """
        Generate HTML template for payment success email.

        Args:
            plan_name: Name of the purchased plan.
            num_credits: Number of credits purchased.
            features: List of plan features.

        Returns:
            HTML string for email body.
        """
        features_html = ""
        for feature in features:
            icon = "✨" if feature.get("is_highlighted", False) else "✓"
            features_html += f"""
                <li style="margin:8px 0;color:#e5e7eb;font-size:14px">
                    <span style="color:#10b981;font-weight:bold">{icon}</span> {feature.get('title', feature.get('description', ''))}
                </li>
            """  # noqa: E501

        html = f"""
        <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;background:#0f172a;color:#e5e7eb;border-radius:12px;overflow:hidden">
            <div style="padding:24px;background:linear-gradient(135deg, #10b981 0%, #059669 100%);text-align:center">
                <h1 style="margin:0;color:#ffffff;font-size:28px">🎙️ YouDub</h1>
                <p style="margin:8px 0 0;color:#d1fae5;font-size:14px">Doblajes interactivos</p>
            </div>

            <div style="padding:32px">
                <h2 style="color:#10b981;margin:0 0 16px 0">🎉 ¡Gracias por tu compra!</h2>
                <p style="line-height:1.6;margin:0 0 24px 0;font-size:16px">
                    Tu pago ha sido procesado exitosamente. ¡Ahora tienes acceso a más doblajes! 🌟
                </p>

                <div style="margin:24px 0;padding:20px;background:#020617;border-radius:8px;border:2px solid #10b981">
                    <h3 style="margin:0 0 12px 0;color:#38bdf8;font-size:20px">Plan adquirido: {plan_name}</h3>
                    <p style="margin:0;font-size:28px;color:#10b981;font-weight:bold">{num_credits} créditos</p>
                </div>

                <div style="margin:24px 0;padding:16px;background:#1e293b;border-radius:8px">
                    <h4 style="margin:0 0 12px 0;color:#38bdf8;font-size:16px">Beneficios incluidos:</h4>
                    <ul style="margin:0;padding-left:20px;list-style:none">
                        {features_html}
                    </ul>
                </div>

                <div style="margin:24px 0;padding:16px;background:#1e293b;border-left:4px solid #10b981;border-radius:4px">
                    <p style="margin:0;font-size:14px;color:#94a3b8">
                        💡 <strong style="color:#10b981">Recordatorio:</strong> Tus créditos no expiran, úsalos cuando quieras.
                    </p>
                </div>

                <p style="font-size:14px;color:#94a3b8;margin:24px 0 0 0;line-height:1.6">
                    ¡Empieza a crear doblajes increíbles ahora! Si tienes alguna pregunta, estamos aquí para ayudarte.
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
    async def send_payment_success_email(
        email: str,
        plan_name: str,
        num_credits: int,
        features: list
    ) -> bool:
        """
        Send payment success confirmation email.

        Args:
            email: Recipient email address.
            plan_name: Name of the purchased plan.
            num_credits: Number of credits purchased.
            features: List of plan features.

        Returns:
            True if email sent successfully, False otherwise.
        """
        try:
            subject = f"🎉 ¡Compra exitosa! - Plan {plan_name}"

            html_content = EmailService._get_payment_success_email_html(
                plan_name, num_credits, features
            )

            params = {
                "from": settings.resend_from_email,
                "to": [email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)

            log_info(
                logger,
                f"Payment success email sent to {email}",
                {"response_id": response.get("id"), "plan": plan_name, "credits": num_credits}
            )
            return True

        except Exception as e:
            log_error(
                logger,
                f"Failed to send payment success email to {email}",
                {"error": str(e)}
            )
            return False
