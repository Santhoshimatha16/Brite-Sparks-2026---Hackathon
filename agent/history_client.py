import requests

class HistoryClient:
    def __init__(self, base_url="http://127.0.0.1:8083"):
        self.base_url = base_url

    def get_resident(self, resident_ref):
        response = requests.get(f"{self.base_url}/residents/{resident_ref}")
        response.raise_for_status()
        return response.json()

    def get_household(self, resident_ref):
        response = requests.get(f"{self.base_url}/residents/{resident_ref}/household")
        response.raise_for_status()
        data = response.json()
        return data.get("household", []) if isinstance(data, dict) else data

    def get_events(self, resident_ref):
        response = requests.get(f"{self.base_url}/residents/{resident_ref}/events")
        response.raise_for_status()
        data = response.json()
        return data.get("events", []) if isinstance(data, dict) else data

    def get_full_history(self, resident_ref):
        """Fetches full resident record, household, and events."""
        full_rec = self.get_resident(resident_ref)
        household = full_rec.get("household", [])
        events = full_rec.get("events", [])
        return {
            "resident": full_rec,
            "household": household,
            "events": events
        }
