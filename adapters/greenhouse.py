# greenhouse.py — Playwright version
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from .base import BaseAdapter, ApplyResult


class GreenhouseAdapter(BaseAdapter):

    def _extract_board_and_job(self, job_url: str):
        m = re.search(r'greenhouse\.io/([\w-]+)/jobs/(\d+)', job_url)
        if m:
            return m.group(1), m.group(2)
        qs = parse_qs(urlparse(job_url).query)
        gh_jid = qs.get("gh_jid", [None])[0]
        if gh_jid:
            return None, gh_jid
        return None, None

    def _fill_field_sync(self, page, selector: str, value: str):
        if not value:
            return
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.fill(value)
                print(f"DEBUG — filled: {selector[:50]} = {value[:30]}")
        except Exception as e:
            print(f"DEBUG — fill error: {e}")

    def _coalesce(self, *values):
        for value in values:
            if value not in (None, ""):
                return value
        return ""

    def _normalize_country(self, value: str) -> str:
        if not value:
            return "United States"
        value = str(value).strip()
        if "united states" in value.lower():
            return "United States"
        return value

    def _build_dropdown_map(self, answers: dict) -> dict:
        return {
            "country": self._normalize_country(self._coalesce(self.profile.country, answers.get("country"), answers.get("United States"), "United States")),
            "state": self._coalesce(self.profile.state, answers.get("state"), self.profile.location_city, self.profile.city, "New York"),
            "location": self._coalesce(self.profile.location_city, self.profile.city, self.profile.state, ""),
            "sponsorship": self._coalesce(answers.get("requires_sponsorship"), answers.get("sponsorship"), "No"),
            "visa": self._coalesce(answers.get("visa_sponsorship"), answers.get("visa"), "No"),
            "immigration": self._coalesce(answers.get("requires_sponsorship"), answers.get("immigration"), "No"),
            "authorized": self._coalesce(answers.get("authorized_to_work"), answers.get("authorized"), "Yes"),
            "legally authorized": self._coalesce(answers.get("authorized_to_work"), answers.get("authorized"), "Yes"),
            "legally authorized to work": self._coalesce(answers.get("authorized_to_work"), answers.get("authorized"), "Yes"),
            "authorization to work": self._coalesce(answers.get("authorized_to_work"), answers.get("authorized"), "Yes"),
            "open to working in-person": self._coalesce(answers.get("open_to_inperson"), answers.get("working_in_person"), "Yes"),
            "relocation": self._coalesce(answers.get("open_to_relocation"), answers.get("relocation"), "Yes"),
            "gender": self._coalesce(answers.get("gender"), "Decline to self-identify"),
            "hispanic": self._coalesce(answers.get("hispanic_latino"), "No"),
            "veteran": self._coalesce(answers.get("veteran_status"), "I am not a protected veteran"),
            "disability": self._coalesce(answers.get("disability"), "No, I do not have a disability"),
            "interviewed": self._coalesce(answers.get("interviewed_before"), "No"),
            "ai policy": self._coalesce(answers.get("ai_policy"), "Yes"),
        }

    def _build_text_field_map(self, answers: dict) -> dict:
        return {
            "city": self._coalesce(self.profile.city, self.profile.location_city, answers.get("city"), ""),
            "state": self._coalesce(self.profile.state, answers.get("state"), self.profile.location_city, self.profile.city, ""),
            "legal first": self._coalesce(self.profile.legal_first_name, self.profile.first_name, answers.get("legal_first_name"), ""),
            "legal last": self._coalesce(self.profile.legal_last_name, self.profile.last_name, answers.get("legal_last_name"), ""),
            "linkedin": self._coalesce(self.profile.linkedin_url, answers.get("linkedin_url"), ""),
            "pronounce": self._coalesce(answers.get("pronounce_name"), answers.get("pronounce"), ""),
            "github": self._coalesce(answers.get("github_url"), answers.get("github"), ""),
            "publication": self._coalesce(answers.get("publications_url"), answers.get("publication"), ""),
            "earliest": self._coalesce(answers.get("earliest_start"), answers.get("earliest"), "Immediately"),
            "deadline": self._coalesce(answers.get("deadlines"), answers.get("deadline"), ""),
            "why": self._coalesce(answers.get("why_company"), answers.get("why_anthropic"), answers.get("why"), ""),
            "impressive": self._coalesce(answers.get("impressive_work"), answers.get("impressive"), ""),
            "additional": self._coalesce(answers.get("additional_info"), answers.get("additional"), ""),
            "address": self._coalesce(answers.get("work_address"), answers.get("address"), self.profile.city, self.profile.location_city, ""),
            "country": self._normalize_country(self._coalesce(self.profile.country, answers.get("country"), "United States")),
        }

    def _pick_value_for_context(self, label_text: str, answers: dict) -> str:
        label = (label_text or "").lower()
        if any(token in label for token in ["country", "nationality", "citizenship", "residence"]):
            return self._normalize_country(self._coalesce(self.profile.country, answers.get("country"), "United States"))
        if any(token in label for token in ["city", "where are you", "where do you live", "work location", "residing", "located"]):
            if "city" in label and self.profile.city:
                return self.profile.city
            if "state" in label and self.profile.state:
                return self.profile.state
            return self._coalesce(self.profile.location_city, self.profile.city, self.profile.state, self.profile.country, "")
        if any(token in label for token in ["location"]):
            return self._coalesce(self.profile.location_city, self.profile.city, self.profile.state, self.profile.country, "")
        if any(token in label for token in ["authorized", "authorization", "eligible", "work authorization", "legally"]):
            return self._coalesce(answers.get("authorized_to_work"), answers.get("authorized"), "Yes")
        return ""

    def _handle_dropdowns(self, page, answers: dict):
        dropdown_map = self._build_dropdown_map(answers)
        text_field_map = self._build_text_field_map(answers)

        try:
            # ── Select dropdowns ──────────────────────────────────────────────
            # Greenhouse ke dropdowns "div.select__container" mein aate hain — usme
            # ek <label> aur EK of these do cheezein hoti hain: (a) real <select>
            # (rare, screen-reader-only) ya (b) custom react-select "select-shell"
            # combobox div (jo actual UI mein dikhta hai). id sirf hidden <input>
            # pe hoti hai, shell div pe nahi — isliye container-level se label lo.
            containers = page.locator("div[class*='select__container']")
            count = containers.count()
            print(f"DEBUG — found {count} dropdown containers")

            for i in range(count):
                container = containers.nth(i)

                label = container.locator("label")
                label_text = label.first.inner_text().lower() if label.count() > 0 else ""

                print(f"DEBUG — dropdown {i}: label={label_text[:80]}")

                matched_keyword, matched_answer = None, None
                label_lower = label_text.lower()

                authorization_tokens = [
                    "legally authorized",
                    "authorized to work",
                    "work authorization",
                    "authorization to work",
                    "authorization",
                    "eligible to work",
                    "eligible to work in the us",
                    "work in the us",
                    "authorized",
                ]
                if any(token in label_lower for token in authorization_tokens):
                    matched_keyword, matched_answer = "authorization", self._coalesce(
                        answers.get("authorized_to_work"),
                        answers.get("authorized"),
                        "Yes",
                    )

                if not matched_answer:
                    for keyword, answer in dropdown_map.items():
                        if not answer:
                            continue
                        keyword_lower = keyword.lower()
                        if keyword_lower in label_lower or keyword_lower.replace(" ", "") in label_lower.replace(" ", ""):
                            if keyword_lower in {"location", "state", "country"}:
                                matched_keyword, matched_answer = keyword, answer
                                break
                            if keyword_lower in {"sponsorship", "visa", "immigration", "relocation", "gender", "hispanic", "veteran", "disability", "interviewed", "ai policy", "open to working in-person"}:
                                matched_keyword, matched_answer = keyword, answer
                                break

                if not matched_answer:
                    context_value = self._pick_value_for_context(label_text, answers)
                    if context_value:
                        matched_keyword, matched_answer = "context", context_value

                if not matched_answer:
                    continue

                # Case 1 — real native <select> andar hai
                native_select = container.locator("select")
                if native_select.count() > 0:
                    try:
                        native_select.first.select_option(label=matched_answer)
                        print(f"DEBUG — set (native): {matched_keyword} = {matched_answer}")
                    except Exception:
                        try:
                            native_select.first.select_option(value=matched_answer)
                        except Exception as e2:
                            print(f"DEBUG — native select failed: {matched_keyword} — {e2}")
                    continue

                # Case 2 — custom react-select "select-shell" combobox
                try:
                    shell = container.locator("[class*='select-shell']").first
                    shell.click()
                    page.wait_for_timeout(300)

                    # Menu options usually render with role="option", or as
                    # divs/li carrying the visible text — try in order.
                    option = page.get_by_role("option", name=matched_answer, exact=False)
                    if option.count() == 0:
                        option = page.locator("[class*='option']", has_text=matched_answer)
                    if option.count() == 0:
                        option = page.locator("li", has_text=matched_answer)

                    if option.count() > 0:
                        option.first.click()
                        print(f"DEBUG — set (custom-click): {matched_keyword} = {matched_answer}")
                    else:
                        # Fallback — type into the open combobox and press Enter,
                        # works for react-select's built-in search/filter input.
                        page.keyboard.type(matched_answer, delay=50)
                        page.wait_for_timeout(300)
                        page.keyboard.press("Enter")
                        print(f"DEBUG — set (custom-type): {matched_keyword} = {matched_answer}")
                except Exception as e:
                    print(f"DEBUG — custom select failed: {matched_keyword} — {e}")

            # Saare inputs/textareas pe label check karo
            all_inputs = page.locator("input[type='text'], textarea")
            inp_count = all_inputs.count()
            print(f"DEBUG — found {inp_count} text inputs")

            for i in range(inp_count):
                inp = all_inputs.nth(i)
                inp_id = inp.get_attribute("id") or ""

                # Label dhundo
                label = page.locator(f'label[for="{inp_id}"]')
                label_text = ""
                if label.count() > 0:
                    label_text = label.first.inner_text().lower()

                for keyword, value in text_field_map.items():
                    if value and keyword.lower() in label_text:
                        try:
                            inp.fill(value)
                            print(f"DEBUG — text field set: {keyword} = {value[:30]}")
                        except Exception as e:
                            print(f"DEBUG — text field failed: {keyword} — {e}")
                        break

        except Exception as e:
            print(f"DEBUG — handler error: {e}")

    def _run_playwright(self, job_url: str, resume_path: Path, job_id: str) -> ApplyResult:
        """Sync Playwright — thread mein chalta hai"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            # Step 1: Page open karo
            print(f"DEBUG — opening: {job_url}")
            page.goto(job_url, wait_until="networkidle", timeout=30000)

            # Step 2: Cookie popup close karo
            try:
                cookie_btn = page.locator(
                    "button:has-text('Accept'), button:has-text('Accept All'), "
                    "button:has-text('I Accept'), button:has-text('Agree'), "
                    "button:has-text('OK'), button:has-text('Got it'), "
                    "[aria-label='Accept'], .consent-modal button"
                )
                if cookie_btn.count() > 0:
                    cookie_btn.first.click()
                    page.wait_for_timeout(1000)
                    print("DEBUG — cookie popup closed")
            except Exception as e:
                print(f"DEBUG — cookie popup error: {e}")

            # Step 3: Apply button click karo
            try:
                apply_btn = page.locator(
                    'button[aria-label="Apply"], '
                    'a[href="#applynow"], '
                    'button:has-text("Apply now"), '
                    'a:has-text("Apply now"), '
                    'button:has-text("Apply for this job"), '
                    'a:has-text("Apply for this job")'
                )
                if apply_btn.count() > 0:
                    apply_btn.first.click()
                    page.wait_for_timeout(2000)
                    print("DEBUG — Apply button clicked")
                else:
                    # Fallback — scroll to form directly
                    page.evaluate("document.querySelector('#application-form, #applynow, .application--container')?.scrollIntoView()")
                    page.wait_for_timeout(1000)
                    print("DEBUG — scrolled to form directly")
            except Exception as e:
                print(f"DEBUG — Apply button error: {e}")

            # Debug — kaunse input fields hain
            inputs = page.locator("input[type='text'], input[type='email'], input[type='tel']")
            count = inputs.count()
            print(f"DEBUG — total input fields found: {count}")
            for i in range(min(count, 10)):
                inp = inputs.nth(i)
                name = inp.get_attribute("name") or ""
                id_ = inp.get_attribute("id") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                print(f"DEBUG — input {i}: name={name}, id={id_}, placeholder={placeholder}")

            # Step 4: Basic form fill — id aur name dono se try karo
            pd = self.profile
            answers = pd.custom_answers or {}

            self._fill_field_sync(page,
                'input[id="first_name"], input[name="job_application[first_name]"]',
                pd.first_name)
            self._fill_field_sync(page,
                'input[id="last_name"], input[name="job_application[last_name]"]',
                pd.last_name)
            self._fill_field_sync(page,
                'input[id="email"], input[name="job_application[email]"]',
                pd.email)
            self._fill_field_sync(page,
                'input[id="phone"], input[name="job_application[phone]"]',
                pd.phone or "")
            self._fill_field_sync(page,
                'input[id="preferred_first_name"], input[name="job_application[preferred_first_name]"]',
                pd.preferred_first_name or "")
            self._fill_field_sync(page,
                'input[id="job_application_linkedin_url"], input[id*="linkedin"], input[name="job_application[urls][LinkedIn]"]',
                pd.linkedin_url or "")
            self._fill_field_sync(page,
                'input[id="job_application_website"], input[id*="website"], input[name="job_application[urls][Website]"]',
                pd.website or "")
            self._fill_field_sync(page,
                'input[id="location_autocomplete"], input[id*="location"], input[name*="location"]',
                pd.location_city or "")

            if pd.cover_letter:
                self._fill_field_sync(page,
                    'textarea[id*="cover_letter"], textarea[name*="cover_letter"]',
                    pd.cover_letter)

            # Step 5: Custom text fields
            self._fill_field_sync(page,
                'input[id*="pronounce"], textarea[id*="pronounce"], '
                'input[placeholder*="pronounce"], textarea[placeholder*="pronounce"]',
                answers.get("pronounce_name", ""))

            self._fill_field_sync(page,
                'input[id*="publication"], input[name*="publication"]',
                answers.get("publications_url", ""))

            self._fill_field_sync(page,
                'input[id*="github"], input[name*="github"]',
                answers.get("github_url", ""))

            self._fill_field_sync(page,
                'textarea[id*="earliest"], input[id*="earliest"]',
                answers.get("earliest_start", "Immediately"))

            self._fill_field_sync(page,
                'textarea[id*="deadline"], input[id*="deadline"]',
                answers.get("deadlines", ""))

            self._fill_field_sync(page,
                'textarea[id*="why"], input[id*="why"]',
                answers.get("why_company", ""))

            self._fill_field_sync(page,
                'textarea[id*="impressive"], textarea[id*="low_level"], textarea[id*="performance"]',
                answers.get("impressive_work", ""))

            self._fill_field_sync(page,
                'textarea[id*="additional"], textarea[id*="extra"]',
                answers.get("additional_info", ""))

            self._fill_field_sync(page,
                'input[id*="address"], input[id*="work_address"]',
                answers.get("work_address", pd.city or pd.location_city or ""))

            # Step 6: Resume upload
            try:
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    file_input.first.set_input_files(str(resume_path))
                    print("DEBUG — resume uploaded")
                    page.wait_for_timeout(5000)
                    print("DEBUG — waited for upload to settle")

                    # Greenhouse sometimes validates the file attachment asynchronously.
                    # Wait for the upload helper / validation state to settle before submit.
                    try:
                        page.wait_for_selector(
                            "text=Uploading, text=uploaded, text=Resume, text=CV",
                            timeout=5000
                        )
                    except Exception:
                        pass
                else:
                    print("DEBUG — file input nahi mila")
            except Exception as e:
                print(f"DEBUG — resume upload error: {e}")

            # Step 7: Dropdowns handle karo
            self._handle_dropdowns(page, answers)

            # Step 8: Screenshot before submit (full page)
            page.screenshot(path="greenhouse_before_submit.png", full_page=True)
            print("DEBUG — screenshot saved: greenhouse_before_submit.png")

            # Step 9: Submit
            submit_btn = page.locator(
                'input[type="submit"], button[type="submit"], '
                'button:has-text("Submit"), button:has-text("Apply for this job"), '
                'button:has-text("Submit Application")'
            )
            if submit_btn.count() == 0:
                browser.close()
                return ApplyResult(
                    success=False, platform="greenhouse",
                    job_id=job_id, error="Submit button nahi mila"
                )

            # Give Greenhouse a short window to finish re-validating the form.
            page.wait_for_timeout(1500)
            submit_btn.first.click()
            print("DEBUG — submit clicked")

            # Some Greenhouse flows present a second submit action after OTP / verification.
            # Wait for the later button to appear in the DOM instead of assuming it exists after a blind delay.
            try:
                post_otp_submit = page.locator(
                    'button:has-text("Submit Application"), '
                    'button:has-text("Submit"), '
                    'button:has-text("Apply for this job"), '
                    'input[type="submit"], button[type="submit"]'
                )
                if post_otp_submit.count() > 0:
                    post_otp_submit.first.click()
                    print("DEBUG — post-OTP submit clicked")
                else:
                    page.wait_for_selector(
                        'button:has-text("Submit Application"), button:has-text("Submit"), button:has-text("Apply for this job")',
                        timeout=30000
                    )
                    page.locator(
                        'button:has-text("Submit Application"), '
                        'button:has-text("Submit"), '
                        'button:has-text("Apply for this job")'
                    ).first.click()
                    print("DEBUG — post-OTP submit clicked after waiting")
            except Exception as e:
                print(f"DEBUG — post-OTP submit click error: {e}")

            # Step 10: Confirmation check
            try:
                page.wait_for_selector(
                    "text=Thank you, text=Application submitted, text=successfully submitted",
                    timeout=120000
                )
                print("DEBUG — SUCCESS! Application submitted")
                browser.close()
                return ApplyResult(success=True, platform="greenhouse", job_id=job_id, error="")

            except Exception:
                current_url = page.url
                page_text = page.inner_text("body")
                page.screenshot(path="greenhouse_after_submit.png", full_page=True)
                page_text_lower = page_text.lower()
                current_url_lower = current_url.lower()
                print("DEBUG — ===== POST-SUBMIT DIAGNOSTICS =====")
                print(f"DEBUG — after submit URL: {current_url}")
                print(f"DEBUG — page title: {page.title()}")
                print(f"DEBUG — page text (1000): {page_text[:1000]}")
                print(f"DEBUG — contains 'confirmation': {'confirmation' in current_url_lower or 'confirmation' in page_text_lower}")
                print(f"DEBUG — contains 'thank': {'thank' in current_url_lower or 'thank' in page_text_lower}")
                print(f"DEBUG — contains 'submitted': {'submitted' in current_url_lower or 'submitted' in page_text_lower}")
                print(f"DEBUG — contains 'success': {'success' in current_url_lower or 'success' in page_text_lower}")
                print(f"DEBUG — contains 'otp': {'otp' in page_text_lower or 'one-time' in page_text_lower or 'verification code' in page_text_lower}")
                print("DEBUG — ===== END POST-SUBMIT DIAGNOSTICS =====")
                browser.close()

                if any(token in current_url_lower for token in ["confirmation", "thank", "submitted", "success"]) or any(token in page_text_lower for token in ["confirmation", "thank", "submitted", "success"]):
                    return ApplyResult(success=True, platform="greenhouse", job_id=job_id, error="")

                if any(token in page_text_lower for token in ["otp", "one-time", "verification code", "code"]):
                    return ApplyResult(
                        success=False, platform="greenhouse",
                        job_id=job_id,
                        error="OTP / verification step detected; user must complete it manually."
                    )

                return ApplyResult(
                    success=False, platform="greenhouse",
                    job_id=job_id,
                    error=f"Confirmation nahi mili. URL: {current_url} | Text: {page_text[:200]}"
                )

    async def apply(self, job_url: str) -> ApplyResult:
        board, job_id = self._extract_board_and_job(job_url)

        if not job_id:
            return ApplyResult(success=False, platform="greenhouse",
                               job_id="", error="Job ID parse nahi hua")
        if not board:
            return ApplyResult(success=False, platform="greenhouse",
                               job_id=job_id, error="Board nahi mila")

        resume_path = Path(__file__).parent.parent / self.profile.resume_path
        if not resume_path.exists():
            return ApplyResult(success=False, platform="greenhouse",
                               job_id=job_id, error=f"Resume nahi mili: {resume_path}")

        print(f"DEBUG — board: {board}, job_id: {job_id}, url: {job_url}")

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, self._run_playwright, job_url, resume_path, job_id
            )
        return result