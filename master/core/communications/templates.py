"""
Email Templates

HTML email templates for verification, password reset, and notifications.
Now uses Jinja2 EmailRenderer.
"""
from master.core.communications.renderer import get_renderer

def render_verification_email(code: str, user_name: str = None, login_url: str = None) -> tuple:
    """
    Render email verification template.
    Returns (subject, html, text)
    """
    subject = f"Verify your email - Code: {code}"
    
    # Default login URL
    if not login_url:
        login_url = "https://wp.zimpricecheck.com/login"
        
    context = {
        "code": code,
        "user_name": user_name,
        "login_url": login_url
    }
    
    html = get_renderer().render("auth/verify_email.html", context)
    
    # Simple text fallback (could be improved with another template or strip_tags)
    text = f"Verify your email. Code: {code}. Login to verify: {login_url}"
    
    return subject, html, text


def render_email_change_email(code: str, new_email: str, user_name: str = None) -> tuple:
    """
    Render email change verification template.
    Returns (subject, html, text)
    """
    subject = f"Confirm email change - Code: {code}"
    
    context = {
        "code": code,
        "new_email": new_email,
        "user_name": user_name
    }
    
    html = get_renderer().render("auth/email_change.html", context)
    text = f"Confirm email change to {new_email}. Code: {code}"
    
    return subject, html, text


def render_magic_link_email(link: str, user_name: str = None, expires_minutes: int = 15) -> tuple:
    """
    Render magic link login template.
    Returns (subject, html, text)
    """
    subject = "Your login link"
    
    context = {
        "magic_link": link,
        "user_name": user_name,
        "expiration_minutes": expires_minutes
    }
    
    html = get_renderer().render("auth/magic_login.html", context)
    text = f"Login link: {link} (Expires in {expires_minutes} minutes)"
    
    return subject, html, text


def render_notification_email(
    title: str,
    message: str,
    user_name: str = None,
    action_url: str = None,
    action_text: str = None,
) -> tuple:
    """
    Render generic notification template.
    Returns (subject, html, text)
    """
    context = {
        "title": title,
        "message": message,
        "user_name": user_name,
        "action_url": action_url,
        "action_text": action_text
    }
    
    html = get_renderer().render("guiding/notification.html", context)
    
    text = f"{title}\n\n{message}"
    if action_url:
        text += f"\n\n{action_text}: {action_url}"
        
    return title, html, text

def render_mfa_email(otp: str, user_name: str = None) -> tuple:
    """
    Render MFA code template.
    Returns (subject, html, text)
    """
    subject = "Your Login Verification Code"
    
    context = {
        "otp": otp,
        "user_name": user_name
    }
    
    html = get_renderer().render("auth/mfa_code.html", context)
    text = f"Your verification code is: {otp}. It expires in 5 minutes."
    
    return subject, html, text
