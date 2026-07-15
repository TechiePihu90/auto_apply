from .greenhouse import GreenhouseAdapter
from .workday    import WorkdayAdapter
from .lever      import LeverAdapter
from .jazzhr     import JazzHRAdapter
from .usajobs    import USAJobsAdapter

PLATFORM_MAP = {
    "boards.greenhouse.io":  GreenhouseAdapter,
    "myworkdayjobs.com":     WorkdayAdapter,
    "wd1.myworkday.com":     WorkdayAdapter,
    "jobs.lever.co":         LeverAdapter,
    "jazz.co":               JazzHRAdapter,
    "app.jazz.co":           JazzHRAdapter,
    "usajobs.gov":           USAJobsAdapter,
}

def get_adapter(job_url: str, profile):
    url = job_url.lower()
    for domain, adapter_cls in PLATFORM_MAP.items():
        if domain in url:
            return adapter_cls(profile)
    raise ValueError(f"Unsupported platform for URL: {job_url}")
