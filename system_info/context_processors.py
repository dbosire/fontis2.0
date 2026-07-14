from .services import get_settings_dict


def site_settings(request):
    return {"fontis_site": get_settings_dict()}
