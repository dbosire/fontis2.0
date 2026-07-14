from django.core.cache import cache

from .models import SystemInfo

CACHE_KEY = "system_info_settings"
DEFAULTS = {
    "name": "Fontis Springs",
    "short_name": "Fontis Springs",
    "logo": "",
    "user_avatar": "",
    "cover": "",
}


def get_settings_dict():
    settings_dict = cache.get(CACHE_KEY)
    if settings_dict is None:
        settings_dict = {**DEFAULTS, **dict(SystemInfo.objects.values_list("meta_field", "meta_value"))}
        cache.set(CACHE_KEY, settings_dict, timeout=None)
    return settings_dict


def get_setting(key, default=None):
    return get_settings_dict().get(key, default)


def set_setting(key, value):
    obj, _ = SystemInfo.objects.get_or_create(meta_field=key, defaults={"meta_value": value})
    if obj.meta_value != value:
        obj.meta_value = value
        obj.save(update_fields=["meta_value"])
    cache.delete(CACHE_KEY)
