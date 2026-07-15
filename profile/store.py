import json, os
from adapters.base import UserProfile

# In production replace with DB lookup
PROFILES_DIR = os.path.join(os.path.dirname(__file__), "data")

async def load_profile(user_id: str) -> UserProfile:
    path = os.path.join(PROFILES_DIR, f"{user_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Profile not found for user: {user_id}")
    with open(path) as f:
        data = json.load(f)
    return UserProfile(**data)

async def save_profile(user_id: str, profile: UserProfile):
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = os.path.join(PROFILES_DIR, f"{user_id}.json")
    with open(path, "w") as f:
        import dataclasses
        json.dump(dataclasses.asdict(profile), f, indent=2)
