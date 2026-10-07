from django.conf import settings
from django.core.files.storage import FileSystemStorage


def get_compliance_storage():
    """Private store for licences, medical certificates and the like. Deliberately
    not under MEDIA_ROOT/MEDIA_URL: nothing here is publicly served — every download
    goes through compliance.views.ComplianceFileView, which checks the user's role."""
    return FileSystemStorage(location=settings.COMPLIANCE_ROOT)
