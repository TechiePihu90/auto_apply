import httpx, re
from .base import BaseAdapter, ApplyResult

class LeverAdapter(BaseAdapter):
    """Uses Lever public Apply API — no browser needed."""

    async def apply(self, job_url: str) -> ApplyResult:
        match = re.search(r'lever\.co/([\w-]+)/([\w-]+)', job_url)
        if not match:
            return ApplyResult(success=False, platform="lever",
                               job_id="", error="Could not parse Lever URL")
        company, posting_id = match.group(1), match.group(2)

        async with httpx.AsyncClient(timeout=30) as client:
            with open(self.profile.resume_path, 'rb') as f:
                resp = await client.post(
                    f"https://api.lever.co/v0/postings/{company}/{posting_id}/apply",
                    files={"resume": ("resume.pdf", f, "application/pdf")},
                    data={
                        "name":             f"{self.profile.first_name} {self.profile.last_name}",
                        "email":            self.profile.email,
                        "phone":            self.profile.phone,
                        "urls[LinkedIn]":   self.profile.linkedin_url,
                        "comments":         self.profile.cover_letter,
                    }
                )

        ok = resp.status_code in (200, 201)
        data = resp.json() if ok else {}
        return ApplyResult(
            success=ok, platform="lever", job_id=posting_id,
            confirmation_id=str(data.get("applicationId", "")),
            error="" if ok else resp.text
        )
