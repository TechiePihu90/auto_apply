import asyncio
from playwright.async_api import async_playwright
from .base import BaseAdapter, ApplyResult

class JazzHRAdapter(BaseAdapter):
    """Uses Playwright headless browser for JazzHR forms."""

    async def apply(self, job_url: str) -> ApplyResult:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(job_url, wait_until="networkidle", timeout=30000)

                await page.fill('input[name="firstname"], input[id*="first"]',
                                self.profile.first_name)
                await page.fill('input[name="lastname"], input[id*="last"]',
                                self.profile.last_name)
                await page.fill('input[name="email"], input[type="email"]',
                                self.profile.email)
                await page.fill('input[name="phone"], input[type="tel"]',
                                self.profile.phone)

                resume_input = page.locator('input[type="file"]').first
                await resume_input.set_input_files(self.profile.resume_path)
                await asyncio.sleep(2)

                await page.click('button[type="submit"], input[type="submit"]')
                await page.wait_for_timeout(3000)

                success = (
                    "thank you" in (await page.title()).lower() or
                    await page.locator("text=Thank you").count() > 0
                )

                return ApplyResult(success=success, platform="jazzhr", job_id=job_url,
                                   error="" if success else "Submission status unclear")

            except Exception as e:
                await page.screenshot(path=f"jazzhr_error_{hash(job_url)}.png")
                return ApplyResult(success=False, platform="jazzhr",
                                   job_id=job_url, error=str(e))
            finally:
                await browser.close()
