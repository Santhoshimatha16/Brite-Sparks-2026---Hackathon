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
        return response.json()

    def get_events(self, resident_ref):
        response = requests.get(f"{self.base_url}/residents/{resident_ref}/events")
        response.raise_for_status()
        return response.json()

    def get_full_history(self, resident_ref):
        """Fetches resident, household, and events in one go."""
        return {
            "resident": self.get_resident(resident_ref),
            "household": self.get_household(resident_ref),
            "events": self.get_events(resident_ref)
        }
