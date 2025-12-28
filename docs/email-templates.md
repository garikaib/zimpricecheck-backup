# Email Templates

This document describes the email templating system used by the WordPress Backup SaaS Master Server.

## Overview

The system uses **Jinja2** for rendering HTML emails. Templates are located in `master/core/templates/email/`.

## Directory Structure

```
master/core/templates/email/
├── base.html                      # Master layout with header, footer, and styling
├── macros/
│   └── components.html            # Reusable UI elements (buttons, alerts)
├── auth/
│   ├── magic_login.html           # Magic link login emails
│   ├── mfa_code.html              # MFA verification codes
│   ├── verify_email.html          # Email verification codes
│   └── email_change.html          # Email change confirmation
└── guiding/
    └── notification.html          # General notifications
```

## Usage

Templates are rendered through the `EmailRenderer` service:

```python
from master.core.communications.renderer import get_renderer

renderer = get_renderer()
html = renderer.render("auth/magic_login.html", {
    "magic_link": "https://...",
    "user_name": "John Doe",
    "expiration_minutes": 15
})
```

Helper functions in `master/core/communications/templates.py` provide backward-compatible wrappers:

```python
from master.core.communications.templates import render_magic_link_email

subject, html, text = render_magic_link_email(
    link="https://...",
    user_name="John Doe"
)
```

## Design

The email design follows a high-contrast Orange/Black/White theme:

- **Header**: Clean white area with logo
- **Hero**: Orange background with uppercase title
- **Body**: White background, readable typography
- **Footer**: Dark gray with copyright and links

## Adding New Templates

1. Create a new `.html` file in the appropriate subdirectory.
2. Extend `base.html`:
   ```jinja
   {% extends "base.html" %}
   {% from "macros/components.html" import button, alert %}
   
   {% block title %}Your Title{% endblock %}
   {% block hero_text %}HERO TEXT{% endblock %}
   
   {% block content %}
   <p>Your content here.</p>
   {{ button(url, "Button Text") }}
   {% endblock %}
   ```
3. Add a helper function to `templates.py` if needed.

## Available Macros

### `button(url, text, variant='primary')`

Renders a styled button. Variants: `primary` (black) or `secondary` (outlined).

### `alert(text, type='info')`

Renders an alert box with left border.
