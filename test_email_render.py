import sys
import os

# Add master to path
sys.path.append(os.getcwd())

from master.core.communications.renderer import get_renderer
from master.core.communications.templates import (
    render_magic_link_email,
    render_verification_email,
    render_mfa_email,
    render_notification_email
)

def test_renderer():
    print("Testing Email Renderer...")
    
    renderer = get_renderer()
    print(f"Template dir: {renderer.template_dir}")
    
    # Test 1: Magic Link
    print("\nTesting Magic Link Render:")
    subj, html, text = render_magic_link_email("http://example.com/login?token=123", "John Doe")
    print(f"Subject: {subj}")
    print(f"HTML len: {len(html)}")
    if "John Doe" in html and "http://example.com/login?token=123" in html:
        print("PASS: Content found")
    else:
        print("FAIL: Content missing")
        print("DEBUG HTML:")
        print(html)
        
    # Test 2: MFA
    print("\nTesting MFA Render:")
    subj, html, text = render_mfa_email("123456", "Jane Doe")
    print(f"Subject: {subj}")
    if "123456" in html and "Jane Doe" in html:
        print("PASS: Content found")
    else:
        print("FAIL: Content missing")

if __name__ == "__main__":
    test_renderer()
