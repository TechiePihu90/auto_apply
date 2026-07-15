# Auto Apply

One-click job application system for Greenhouse, Workday, Lever, JazzHR, and USAJobs.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # fill in your API keys
```

## Run

```bash
uvicorn main:app --reload
```
http://127.0.0.1:8000/docs
## API

**POST /apply**
```json
{
  "user_id": "sample_user",
  "job_url": "https://boards.greenhouse.io/acme/jobs/12345",
  "job_id":  "12345"
}
```

**GET /results/{user_id}** — list all applications for a user

## User Profile

Store profiles as JSON in `profile/data/{user_id}.json`.
See `profile/data/sample_user.json` for the schema.

## Platform coverage

| Platform   | Method            | Notes                          |
|------------|-------------------|--------------------------------|
| Greenhouse | REST API          | No browser needed              |
| Lever      | REST API          | No browser needed              |
| Workday    | Playwright        | Headless Chrome                |
| JazzHR     | Playwright        | Headless Chrome                |
| USAJobs    | REST API          | Requires API key from developer.usajobs.gov |

## Adding a new platform

1. Create `adapters/yourplatform.py` extending `BaseAdapter`
2. Implement `async def apply(self, job_url) -> ApplyResult`
3. Add the domain → class mapping in `adapters/__init__.py`
