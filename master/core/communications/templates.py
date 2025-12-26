"""
Email Templates

HTML email templates for verification, password reset, and notifications.
"""

# Base template with consistent branding
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f5;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            padding: 32px;
            margin-top: 20px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #2563eb;
        }}
        .code-box {{
            background: #f0f9ff;
            border: 2px dashed #2563eb;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 24px 0;
        }}
        .code {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 32px;
            font-weight: bold;
            color: #1d4ed8;
            letter-spacing: 4px;
        }}
        .button {{
            display: inline-block;
            background: #2563eb;
            color: white !important;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: 600;
            margin: 16px 0;
        }}
        .button:hover {{
            background: #1d4ed8;
        }}
        .footer {{
            text-align: center;
            color: #6b7280;
            font-size: 12px;
            margin-top: 32px;
        }}
        .warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px;
            margin: 16px 0;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <div class="logo">🔒 WordPress Backup</div>
            </div>
            {content}
        </div>
        <div class="footer">
            <p>This email was sent by WordPress Backup SaaS</p>
            <p>If you didn't request this, please ignore this email.</p>
        </div>
    </div>
</body>
</html>
"""


def render_verification_email(code: str, user_name: str = None, login_url: str = None) -> tuple:
    """
    Render email verification template.
    
    Returns (subject, html, text)
    """
    subject = f"Verify your email - Code: {code}"
    
    greeting = f"Hi {user_name}," if user_name else "Hi there,"
    
    # Default login URL
    if not login_url:
        login_url = "https://wp.zimpricecheck.com/login"
    
    content = f"""
        <h2 style="margin-top: 0;">Email Verification Required</h2>
        <p>{greeting}</p>
        <p>Your account has been created. To complete your registration and access the dashboard, please verify your email address.</p>
        
        <p style="text-align: center;">
            <a href="{login_url}" class="button">Go to Login</a>
        </p>
        
        <p>When prompted, enter this verification code:</p>
        <div class="code-box">
            <div class="code">{code}</div>
        </div>
        <p style="font-size: 14px; color: #6b7280;">
            <strong>How to verify:</strong> Go to the login page and sign in with your email and password. 
            You'll be prompted to enter the verification code above.
        </p>
        <div class="warning">
            ⏱️ This code will expire in 24 hours.
        </div>
    """
    
    html = BASE_TEMPLATE.format(title="Email Verification", content=content)
    text = f"""
Email Verification Required

{greeting}

Your account has been created. To complete your registration and access the dashboard, please verify your email address.

Go to: {login_url}

Your verification code is: {code}

How to verify: Go to the login page and sign in with your email and password. You'll be prompted to enter the verification code above.

This code will expire in 24 hours.
"""
    
    return subject, html, text.strip()


def render_email_change_email(code: str, new_email: str, user_name: str = None) -> tuple:
    """
    Render email change verification template.
    
    Returns (subject, html, text)
    """
    subject = f"Confirm email change - Code: {code}"
    
    greeting = f"Hi {user_name}," if user_name else "Hi there,"
    
    content = f"""
        <h2 style="margin-top: 0;">Email Change Request</h2>
        <p>{greeting}</p>
        <p>A request was made to change your email address to:</p>
        <p style="font-weight: bold; color: #1d4ed8;">{new_email}</p>
        <p>Please provide this code to your administrator to complete the change:</p>
        <div class="code-box">
            <div class="code">{code}</div>
        </div>
        <div class="warning">
            ⚠️ If you did not request this change, please contact your administrator immediately.
        </div>
    """
    
    html = BASE_TEMPLATE.format(title="Email Change", content=content)
    text = f"""
Email Change Request

{greeting}

A request was made to change your email address to: {new_email}

Your confirmation code is: {code}

Please provide this code to your administrator to complete the change.

If you did not request this change, please contact your administrator immediately.
"""
    
    return subject, html, text.strip()


def render_magic_link_email(link: str, user_name: str = None, expires_minutes: int = 15) -> tuple:
    """
    Render magic link login template.
    
    Returns (subject, html, text)
    """
    subject = "Your login link"
    
    greeting = f"Hi {user_name}," if user_name else "Hi there,"
    
    content = f"""
        <h2 style="margin-top: 0;">One-Click Login</h2>
        <p>{greeting}</p>
        <p>Click the button below to log in to your account:</p>
        <p style="text-align: center;">
            <a href="{link}" class="button">Log In Now</a>
        </p>
        <p style="font-size: 14px; color: #6b7280;">
            Or copy and paste this link into your browser:<br>
            <a href="{link}" style="color: #2563eb; word-break: break-all;">{link}</a>
        </p>
        <div class="warning">
            ⏱️ This link will expire in {expires_minutes} minutes.
        </div>
    """
    
    html = BASE_TEMPLATE.format(title="Login Link", content=content)
    text = f"""
One-Click Login

{greeting}

Click the link below to log in to your account:

{link}

This link will expire in {expires_minutes} minutes.
"""
    
    return subject, html, text.strip()


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
    greeting = f"Hi {user_name}," if user_name else "Hi there,"
    
    action_html = ""
    action_text_str = ""
    if action_url and action_text:
        action_html = f'<p style="text-align: center;"><a href="{action_url}" class="button">{action_text}</a></p>'
        action_text_str = f"\n\n{action_text}: {action_url}"
    
    content = f"""
        <h2 style="margin-top: 0;">{title}</h2>
        <p>{greeting}</p>
        <p>{message}</p>
        {action_html}
    """
    
    html = BASE_TEMPLATE.format(title=title, content=content)
    text = f"""
{title}

{greeting}

{message}{action_text_str}
"""
    
    return title, html, text.strip()
