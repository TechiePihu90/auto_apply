from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class UserProfile:
    first_name: str
    last_name: str
    email: str
    phone: str
    resume_path: str
    linkedin_url: str = ""
    cover_letter: str = ""
    preferred_first_name: str = ""
    legal_first_name: str = ""
    legal_last_name: str = ""
    country: str = "United States"
    custom_answers: dict = field(default_factory=dict)
    location_city: str = ""
    city: str = ""
    state: str = ""
    website: str = ""
    interview_accommodations: str = ""
    

@dataclass
class ApplyResult:
    success: bool
    platform: str
    job_id: str
    confirmation_id: str = ""
    error: str = ""
    application_id: str = ""
class BaseAdapter(ABC):
    def __init__(self, profile: UserProfile):
        self.profile = profile

    @abstractmethod
    async def apply(self, job_url: str) -> ApplyResult:
        ...
