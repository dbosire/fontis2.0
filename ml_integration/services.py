import httpx


class MLClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def predict_all(self):
        response = httpx.get(f"{self.base_url}/predict_all/", timeout=10)
        response.raise_for_status()
        data = response.json()
        # v1 returns {"predictions": [...]}, v2 returns a bare [...] — normalize both to a list.
        return data["predictions"] if isinstance(data, dict) else data
