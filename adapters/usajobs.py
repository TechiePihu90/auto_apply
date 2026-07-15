import httpx, re, os
from .base import BaseAdapter, ApplyResult

USAJOBS_API = "https://data.usajobs.gov/api"

class USAJobsAdapter(BaseAdapter):
    """Uses the official USAJobs REST API. Register at developer.usajobs.gov."""

    def __init__(self, profile):
        super().__init__(profile)
        self.api_key    = os.getenv("USAJOBS_API_KEY", "")
        self.user_agent = os.getenv("USAJOBS_USER_AGENT", self.profile.email)

    async def apply(self, job_url: str) -> ApplyResult:
        # Extract control number from URL
        # e.g. https://www.usajobs.gov/job/12345678
        match = re.search(r'usajobs\.gov/job/(\d+)', job_url)
        if not match:
            return ApplyResult(success=False, platform="usajobs",
                               job_id="", error="Could not parse USAJobs URL")
        control_number = match.group(1)

        headers = {
            "Host":            "data.usajobs.gov",
            "User-Agent":      self.user_agent,
            "Authorization-Key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch job details first to get apply URI
            resp = await client.get(
                f"{USAJOBS_API}/search?ControlNumber={control_number}",
                headers=headers
            )
            if resp.status_code != 200:
                return ApplyResult(success=False, platform="usajobs",
                                   job_id=control_number, error=resp.text)

            jobs = resp.json().get("SearchResult", {}).get("SearchResultItems", [])
            if not jobs:
                return ApplyResult(success=False, platform="usajobs",
                                   job_id=control_number, error="Job not found")

            apply_uri = jobs[0]["MatchedObjectDescriptor"].get("ApplyURI", [""])[0]

        # USAJobs requires account login for actual submission;
        # return the direct apply link for browser redirect flow
        return ApplyResult(
            success=True, platform="usajobs", job_id=control_number,
            confirmation_id=apply_uri,
            error="USAJobs requires account auth — redirect user to apply_uri"
        )
