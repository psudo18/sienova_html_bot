"""Entry-point handlers for /extract, /fromjson, /both — thin wrappers"""
from handlers.conversation import (
    extract_handler, json_to_html_handler, html_to_both_handler
)
