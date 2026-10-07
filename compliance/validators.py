import os

from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
MAX_UPLOAD_MB = 10


def validate_upload(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type. Upload one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
    if file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"File is too large (max {MAX_UPLOAD_MB} MB).")
