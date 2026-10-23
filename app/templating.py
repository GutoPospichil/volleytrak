from __future__ import annotations

from fastapi.templating import Jinja2Templates

from .config import TEMPLATE_DIR

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
