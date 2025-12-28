import os
import logging
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

class EmailRenderer:
    """
    Renders HTML emails using Jinja2 templates.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        if not template_dir:
            # Default to master/core/templates/email relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to core, then to templates/email
            # current: .../master/core/communications
            # target:  .../master/core/templates/email
            template_dir = os.path.join(os.path.dirname(current_dir), "templates", "email")
            
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        logger.info(f"EmailRenderer initialized with template dir: {self.template_dir}")

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a Jinja2 template with the provided context.
        
        Args:
            template_name: Path to template relative to template_dir (e.g., 'auth/magic_login.html')
            context: Dictionary of variables to pass to the template
            
        Returns:
            Rendered HTML string
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render email template '{template_name}': {e}")
            raise

# Global instance
_renderer = None

def get_renderer() -> EmailRenderer:
    """Get or create the global EmailRenderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = EmailRenderer()
    return _renderer
