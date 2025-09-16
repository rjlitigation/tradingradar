# app/legal.py
from flask import Blueprint, render_template_string
import markdown, os

legal_bp = Blueprint("legal", __name__)
LEGAL_DIR = os.path.join(os.path.dirname(__file__), "..", "legal")

def load_md(filename):
    with open(os.path.join(LEGAL_DIR, filename), "r", encoding="utf-8") as f:
        return markdown.markdown(f.read())

@legal_bp.route("/terms")
def terms(): return render_template_string(load_md("terms.md"))

@legal_bp.route("/privacy")
def privacy(): return render_template_string(load_md("privacy.md"))

@legal_bp.route("/refund")
def refund(): return render_template_string(load_md("refund.md"))

@legal_bp.route("/cancellation")
def cancellation(): return render_template_string(load_md("cancellation.md"))

@legal_bp.route("/cookies")
def cookies(): return render_template_string(load_md("cookies.md"))

@legal_bp.route("/disclaimer")
def disclaimer(): return render_template_string(load_md("disclaimer.md"))
