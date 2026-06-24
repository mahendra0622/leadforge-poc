# Re-export User from main models package so security.py import works
from app.models import User
__all__ = ["User"]
