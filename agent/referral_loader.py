import json
import os

def load_referrals(filepath="referral-queue.json"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Referral queue file not found at: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
