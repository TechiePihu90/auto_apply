from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from adapters import get_adapter
from profile.store import load_profile
from tracker.db import save_result, get_results

app = FastAPI(title="Auto Apply API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────

class ApplyRequest(BaseModel):
    user_id: str
    job_url: str
    job_id: str
    platform: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "Auto Apply API running"}


@app.post("/apply")
async def apply_job(req: ApplyRequest, bg: BackgroundTasks):
   
    bg.add_task(run_apply, req.user_id, req.job_url, req.job_id)
    return {"status": "queued", "job_id": req.job_id}






@app.get("/results/{user_id}")
async def get_user_results(user_id: str):
    """Get all application results for a user."""
    return await get_results(user_id)


# ── Background task ───────────────────────────────────────────────────────────

async def run_apply(user_id: str, job_url: str, job_id: str):
    try:
        profile = await load_profile(user_id)
        adapter = get_adapter(job_url, profile)
        board, parsed_job_id = adapter._extract_board_and_job(job_url)
        print(f"DEBUG — board: {board}, job_id: {parsed_job_id}, url: {job_url}")
        result  = await adapter.apply(job_url)
       
    except Exception as e:
        from adapters.base import ApplyResult
        result = ApplyResult(success=False, platform="unknown",
                             job_id=job_id, error=str(e))
    await save_result(user_id, job_id, result)