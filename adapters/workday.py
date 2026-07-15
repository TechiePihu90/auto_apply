import asyncio
from playwright.async_api import async_playwright
from .base import BaseAdapter, ApplyResult

# Selectors — update here if Workday changes their data-automation-id values
SELECTORS = {
    "apply_btn":   "text=Apply",
    "first_name":  '[data-automation-id="legalNameSection_firstName"]',
    "last_name":   '[data-automation-id="legalNameSection_lastName"]',
    "email":       '[data-automation-id="email"]',
    "phone":       '[data-automation-id="phone-number"]',
    "resume":      '[data-automation-id="file-upload-input-ref"]',
    "next_btn":    '[data-automation-id="bottom-navigation-next-button"]',
    "submit_btn":  '[data-automation-id="bottom-navigation-next-button"]',
}

class WorkdayAdapter(BaseAdapter):
    """Uses Playwright headless browser — Workday has no public API."""

    async def apply(self, job_url: str) -> ApplyResult:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(job_url, wait_until="networkidle", timeout=30000)
                await page.click(SELECTORS["apply_btn"], timeout=10000)
                await page.wait_for_load_state("networkidle")

                await page.fill(SELECTORS["first_name"], self.profile.first_name)
                await page.fill(SELECTORS["last_name"],  self.profile.last_name)
                await page.fill(SELECTORS["email"],       self.profile.email)
                await page.fill(SELECTORS["phone"],       self.profile.phone)

                await page.set_input_files(SELECTORS["resume"], self.profile.resume_path)
                await asyncio.sleep(2)  # wait for upload

                await page.click(SELECTORS["next_btn"])
                await page.wait_for_timeout(3000)

                success = (
                    "thank you" in (await page.title()).lower() or
                    await page.locator("text=Application submitted").count() > 0 or
                    await page.locator("text=Thank you").count() > 0
                )

                return ApplyResult(
                    success=success, platform="workday", job_id=job_url,
                    error="" if success else "Submit may have failed — check screenshot"
                )

            except Exception as e:
                await page.screenshot(path=f"workday_error_{hash(job_url)}.png")
                return ApplyResult(success=False, platform="workday",
                                   job_id=job_url, error=str(e))
            finally:
                await browser.close()
