import re
import datetime
from playwright.sync_api import sync_playwright
from difflib import get_close_matches, SequenceMatcher

class BrowserController:
    def __init__(self, default_timeout=15000, logger=None):
        self.default_timeout = default_timeout
        self.logger = logger
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def launch_browser(self):
        """Launches the browser if not already running, or reuses the current session."""
        if self.browser:
            try:
                if self.browser.is_connected():
                    return
            except Exception:
                self.close_browser()
                
        if self.logger:
            self.logger.info("Launching Chrome/Chromium browser...")
            
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.default_timeout)

    def close_browser(self):
        """Safely closes the browser and stops Playwright."""
        if self.logger:
            self.logger.info("Closing browser...")
        try:
            if self.page:
                self.page.close()
        except Exception:
            pass
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
            
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def navigate_to_form(self, url):
        """Navigates to the specified Google Form URL."""
        self.launch_browser()
        if self.logger:
            self.logger.info(f"Navigating to form: {url}")
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")

    # ==========================================
    # PHASE 1: SCAN AND PLAN AUTOMATION
    # ==========================================
    def scan_entire_form(self, url, config_dummy_data=None):
        """Phase 1: Performs a full multi-page scan of the form, building and
        executing dummy answer plans for all fields to navigate through all pages.
        Reloads the form at the end to leave it completely clean.
        """
        self.navigate_to_form(url)
        config_dummy_data = config_dummy_data or {}
        
        all_scanned_questions = []
        form_title = "Google Form"
        page_num = 1
        max_page_retries = 3
        
        if self.logger:
            self.logger.info("Starting Phase 1: Full Form Scan")
            
        while True:
            if self.logger:
                self.logger.info(f"Scanning Page {page_num}...")
                
            # 1. Scan current page completely (No filling during this step)
            scan_results = self.scan_current_page(page_num)
            if page_num == 1:
                form_title = scan_results["form_title"]
                
            page_questions = scan_results["questions"]
            
            # Log scanned questions
            for q in page_questions:
                options_log = f" | Options: {', '.join(q['options'])}" if q["options"] else ""
                if self.logger:
                    self.logger.info(f"Found question: {q['label']} | Type: {q['type']} | Required: {q['required']}{options_log}")

            current_labels = [q["label"] for q in page_questions]
            next_btn = scan_results["next_btn"]
            
            # 2. If a Next button exists, we must fill fields to proceed
            if next_btn:
                retry_count = 0
                page_changed = False
                
                while retry_count < max_page_retries:
                    # Build answer plan for Page
                    if self.logger:
                        self.logger.info(f"Building answer plan for Page {page_num} (Attempt {retry_count + 1})...")
                    answer_plan = self.build_answer_plan(page_questions, config_dummy_data)
                    
                    # Fill fields
                    if self.logger:
                        self.logger.info(f"Filling fields for Page {page_num}...")
                    self.fill_required_fields_from_plan(answer_plan)
                    
                    # Validate the page
                    validation_errors = self.validate_current_page()
                    if validation_errors:
                        if self.logger:
                            self.logger.warning(f"Validation errors before Next: {validation_errors}")
                    
                    # Click Next
                    if self.logger:
                        self.logger.info("Clicking Next...")
                    self.click_next_if_available()
                    
                    # Wait and check if the page actually changed
                    self.page.wait_for_timeout(1500)
                    new_scan = self.scan_current_page(page_num)
                    new_labels = [q["label"] for q in new_scan["questions"]]
                    
                    if new_labels != current_labels:
                        # Page changed successfully!
                        page_changed = True
                        all_scanned_questions.extend(page_questions)
                        break
                    else:
                        retry_count += 1
                        if self.logger:
                            self.logger.warning(f"Page did not change after clicking Next.")
                        
                        # Identify failed validation errors on the page
                        validation_errors = self.validate_current_page()
                        if validation_errors:
                            if self.logger:
                                self.logger.warning(f"Validation error found: {validation_errors}")
                                
                        # Re-scan to catch any newly appeared inputs or status
                        page_questions = new_scan["questions"]
                
                if not page_changed:
                    error_msg = f"Failed to navigate past Page {page_num} after {max_page_retries} attempts. Required fields might be invalid or missing."
                    if self.logger:
                        self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
                page_num += 1
            else:
                # No next button, we are on the final page (Submit)
                all_scanned_questions.extend(page_questions)
                if self.logger:
                    self.logger.info("Reached final page (Submit button detected). Scan complete.")
                break
                
        # 3. Reload the form to clear all dummy data and leave it clean
        if page_num > 1:
            if self.logger:
                self.logger.info("Reloading form to clear all temporary dummy data...")
            self.navigate_to_form(url)
            
        return form_title, all_scanned_questions

    def scan_current_page(self, page_num):
        """Scans the DOM of the current page and extracts all questions and buttons."""
        try:
            self.page.wait_for_selector('div[role="listitem"]', timeout=5000)
        except Exception:
            pass

        # Detect Form Title
        form_title = "Google Form"
        title_el = self.page.query_selector('h1, div[role="heading"][aria-level="1"], .F9ypgc')
        if title_el:
            form_title = re.sub(r'\s+', ' ', title_el.inner_text()).strip()

        # Detect Section Title & Description
        section_title = ""
        section_desc = ""
        section_title_el = self.page.query_selector('div[aria-level="2"][role="heading"], .ah57t, h2')
        if section_title_el:
            section_title = re.sub(r'\s+', ' ', section_title_el.inner_text()).strip()
            
        section_desc_el = self.page.query_selector('.c21gof, .pZ45eb')
        if section_desc_el:
            section_desc = re.sub(r'\s+', ' ', section_desc_el.inner_text()).strip()

        questions = []
        containers = self.page.query_selector_all('div[role="listitem"]')
        
        for container in containers:
            # 1. Label
            title_el = container.query_selector('div[role="heading"]')
            if not title_el:
                title_el = container.query_selector('.M7eMe')
                
            if not title_el:
                continue
                
            label_text = title_el.inner_text().strip()
            label_text = re.sub(r'\s+', ' ', label_text).strip()
            
            # 2. Required Status
            is_required = False
            if "*" in label_text:
                is_required = True
                label_text = re.sub(r'\s*\*$', '', label_text).strip()
                
            required_input = container.query_selector('[aria-required="true"]')
            if required_input:
                is_required = True

            # 3. Field Type Detection
            field_type = None
            options = []
            
            checkboxes = container.query_selector_all('div[role="checkbox"]')
            radios = container.query_selector_all('div[role="radio"]')
            listbox = container.query_selector('div[role="listbox"]')
            textarea = container.query_selector('textarea')
            text_input = container.query_selector('input[type="text"]')
            
            date_inputs = container.query_selector_all('input[type="date"]')
            is_date_fields = False
            if not date_inputs:
                month_input = container.query_selector('input[aria-label="Month"]')
                day_input = container.query_selector('input[aria-label="Day"]')
                year_input = container.query_selector('input[aria-label="Year"]')
                if month_input or day_input or year_input:
                    is_date_fields = True
                    
            time_inputs = container.query_selector_all('input[type="time"]')
            is_time_fields = False
            if not time_inputs:
                hour_input = container.query_selector('input[aria-label="Hour"]')
                minute_input = container.query_selector('input[aria-label="Minute"]')
                if hour_input or minute_input:
                    is_time_fields = True

            if checkboxes:
                field_type = "checkbox"
                for cb in checkboxes:
                    label = cb.get_attribute("aria-label") or cb.inner_text() or cb.evaluate("el => el.parentElement.innerText") or ""
                    label = re.sub(r'\s+', ' ', label).strip()
                    options.append(label)
            elif radios:
                field_type = "multiple_choice"
                for rd in radios:
                    label = rd.get_attribute("aria-label") or rd.inner_text() or rd.evaluate("el => el.parentElement.innerText") or ""
                    label = re.sub(r'\s+', ' ', label).strip()
                    options.append(label)
            elif listbox:
                field_type = "dropdown"
                # Scrape dropdown options by temporarily clicking it
                try:
                    listbox_btn = container.query_selector('div[role="listbox"]')
                    if listbox_btn:
                        listbox_btn.click()
                        self.page.wait_for_timeout(300)
                        self.page.wait_for_selector('div[role="option"]', timeout=2000)
                        option_els = self.page.query_selector_all('div[role="option"]')
                        for opt in option_els:
                            if opt.is_visible():
                                opt_text = opt.get_attribute("data-value") or opt.inner_text() or ""
                                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                                if opt_text and opt_text not in options:
                                    options.append(opt_text)
                except Exception:
                    pass
                # Close the dropdown
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(100)
                
            elif is_date_fields or date_inputs:
                field_type = "date"
            elif is_time_fields or time_inputs:
                field_type = "time"
            elif textarea:
                field_type = "paragraph"
            elif text_input:
                field_type = "short_answer"
            else:
                textbox = container.query_selector('div[role="textbox"]')
                if textbox:
                    if textbox.get_attribute("aria-multiline") == "true":
                        field_type = "paragraph"
                    else:
                        field_type = "short_answer"

            if field_type:
                questions.append({
                    "page_number": page_num,
                    "label": label_text,
                    "type": field_type,
                    "required": is_required,
                    "options": options,
                    "locator_strategy": f"question_container > {field_type}",
                    "dummy_answer": "",
                    "filled_during_scan": False,
                    "fill_status": "pending"
                })

        # Scan for email inputs outside standard listitems (e.g. automatic email collection)
        try:
            email_inputs = self.page.query_selector_all('input[type="email"]')
            for email_in in email_inputs:
                already_scanned = False
                for q in questions:
                    if "email" in q["label"].lower() or "e-mail" in q["label"].lower() or "gmail" in q["label"].lower():
                        already_scanned = True
                        break
                
                if not already_scanned:
                    label_text = "Email Address"
                    aria_label = email_in.get_attribute("aria-label")
                    if aria_label:
                        label_text = re.sub(r'\s+', ' ', aria_label).strip()
                    
                    is_req = email_in.get_attribute("required") is not None or email_in.get_attribute("aria-required") == "true" or True
                    questions.insert(0, {
                        "page_number": page_num,
                        "label": label_text,
                        "type": "email",
                        "required": is_req,
                        "options": [],
                        "locator_strategy": "input[type='email']",
                        "dummy_answer": "test.cebu.user@example.com",
                        "filled_during_scan": False,
                        "fill_status": "pending"
                    })
        except Exception:
            pass

        # Scan for text inputs that act as email inputs
        try:
            text_inputs = self.page.query_selector_all('input[type="text"]')
            for txt_in in text_inputs:
                aria_label = txt_in.get_attribute("aria-label") or ""
                autocomplete = txt_in.get_attribute("autocomplete") or ""
                placeholder = txt_in.get_attribute("placeholder") or ""
                
                is_email = False
                if any(kw in aria_label.lower() for kw in ["email", "e-mail", "gmail"]):
                    is_email = True
                elif any(kw in autocomplete.lower() for kw in ["email"]):
                    is_email = True
                elif any(kw in placeholder.lower() for kw in ["email"]):
                    is_email = True
                    
                if is_email:
                    label_name = aria_label if aria_label else "Email Address"
                    label_name = re.sub(r'\s+', ' ', label_name).strip()
                    
                    already_scanned = False
                    for q in questions:
                        if q["label"].lower() == label_name.lower() or "email" in q["label"].lower():
                            already_scanned = True
                            break
                            
                    if not already_scanned:
                        is_req = txt_in.get_attribute("required") is not None or txt_in.get_attribute("aria-required") == "true" or True
                        questions.insert(0, {
                            "page_number": page_num,
                            "label": label_name,
                            "type": "email",
                            "required": is_req,
                            "options": [],
                            "locator_strategy": "input[type='text']",
                            "dummy_answer": "test.cebu.user@example.com",
                            "filled_during_scan": False,
                            "fill_status": "pending"
                        })
        except Exception:
            pass

        next_btn = self._find_button(["Next", "Continue", "Siguiente", "Susunod"])
        back_btn = self._find_button(["Back", "Atrás", "Bumalik"])
        submit_btn = self._find_button(["Submit", "Submit form", "Enviar", "Isumite"])
        clear_btn = self._find_button(["Clear form", "Borrar formulario", "Burahin ang form"])

        return {
            "form_title": form_title,
            "section_title": section_title,
            "section_desc": section_desc,
            "questions": questions,
            "next_btn": next_btn,
            "back_btn": back_btn,
            "submit_btn": submit_btn,
            "clear_btn": clear_btn
        }

    def build_answer_plan(self, questions, config_dummy_data):
        """Builds a dummy answer plan for ALL fields on the current page.
        During Phase 1 scanning, we fill every field (required AND optional)
        to guarantee page navigation succeeds. The form is reloaded clean at the end.
        """
        answer_plan = {}
        for q in questions:
            dummy_val = self.generate_dummy_value(q, config_dummy_data)
            answer_plan[q["label"]] = dummy_val
            q["dummy_answer"] = dummy_val
            req_str = "required" if q["required"] else "optional"
            if self.logger:
                self.logger.info(f"Planned dummy answer ({req_str}): {q['label']} -> {dummy_val}")
        return answer_plan

    def fill_required_fields_from_plan(self, answer_plan):
        """Fills the form fields based on the built answer plan."""
        for q_label, val in answer_plan.items():
            self._fill_single_field(q_label, val)

    def validate_current_page(self):
        """Checks the page for any visible validation error messages."""
        errors = []
        alerts = self.page.query_selector_all('[role="alert"], .RHiWt')
        for alert in alerts:
            if alert.is_visible():
                text = alert.inner_text().strip()
                if text:
                    errors.append(text)
        return errors

    def click_next_if_available(self):
        """Clicks the Next button and waits for the page transition."""
        next_btn = self._find_button(["Next", "Next page", "Continue", "Siguiente", "Susunod"])
        if next_btn:
            next_btn.scroll_into_view_if_needed()
            next_btn.click()
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_timeout(1000)
            return True
        return False

    def generate_dummy_value(self, question, config_dummy_data):
        """Generates a realistic dummy value based on the question type and options."""
        q_label_lower = question["label"].lower()
        q_type = question["type"]
        options = question.get("options", [])

        # Priority 1: Match config dummy data keys
        for key, val in config_dummy_data.items():
            if key in q_label_lower:
                if q_type in ["multiple_choice", "checkbox", "dropdown"]:
                    matched_opt = self._match_option_value(val, options)
                    if matched_opt:
                        return matched_opt
                else:
                    return val

        # Priority 2: Option-based questions (must choose a valid option)
        if q_type in ["multiple_choice", "checkbox", "dropdown"]:
            if options:
                if "age" in q_label_lower:
                    for opt in options:
                        if "above" in opt.lower() or "over" in opt.lower() or "+" in opt:
                            return opt
                if "gpa" in q_label_lower or "grade" in q_label_lower:
                    middle_idx = len(options) // 2
                    return options[middle_idx]
                return options[0]
            return "1"

        # Priority 3: Text fields / Email fields
        if q_type == "email" or any(kw in q_label_lower for kw in ["email", "e-mail", "gmail"]):
            return config_dummy_data.get("email", "test.cebu.user@example.com")

        if q_type in ["short_answer", "paragraph"]:
            if "name" in q_label_lower:
                return config_dummy_data.get("name", "Test User")
            if "student id" in q_label_lower or "id number" in q_label_lower or "student no" in q_label_lower:
                return config_dummy_data.get("student id", "202400001")
            if "phone" in q_label_lower or "mobile" in q_label_lower or "contact" in q_label_lower:
                return config_dummy_data.get("phone", "09123456789")
            return config_dummy_data.get("text", "Test response only")

        # Priority 4: Date & Time
        if q_type == "date":
            return datetime.date.today().strftime("%Y-%m-%d")
        if q_type == "time":
            return "12:00"

        return "Test"

    # ==========================================
    # PHASE 2: FILL FORM WITH REAL DATA
    # ==========================================
    def fill_form_with_real_data(self, mapper, parsed_record, template=None, use_dummy_data=True, config_dummy_data=None, progress_callback=None):
        """Phase 2: Fills the form page-by-page using the user's real parsed data.
        If a required field has no real data, fills it with dummy data if enabled.
        """
        if not self.page:
            raise Exception("Browser page is not loaded.")

        config_dummy_data = config_dummy_data or {}
        page_number = 1
        
        while True:
            if self.logger:
                self.logger.info(f"--- Filling Page {page_number} ---")

            # 1. Scrape questions on the current visible page
            _, questions = self.detect_form_details_on_page()
            
            # 2. Map fields for the current page
            mapped, unmapped, missing_req = mapper.map_fields(parsed_record, questions, template)

            # 3. Fill the fields on this page
            total_fields = len(questions)
            for idx, q in enumerate(questions):
                q_label = q["title"]
                val = None
                is_dummy = False

                if q_label in mapped and str(mapped[q_label]).strip() != "":
                    val = mapped[q_label]
                    is_dummy = False
                elif q["required"]:
                    if use_dummy_data:
                        val = self.generate_dummy_value({"label": q_label, "type": q["type"], "options": q["options"]}, config_dummy_data)
                        is_dummy = True
                        if self.logger:
                            self.logger.warning(f"Required field '{q_label}' has no real data. Using dummy value: '{val}'")
                    else:
                        if self.logger:
                            self.logger.error(f"Missing required field: '{q_label}'")
                
                if val is not None:
                    self._fill_single_field(q_label, val)
                    
                if progress_callback:
                    progress_callback(idx + 1, total_fields)

            # 4. Check for 'Next' button to go to the next page
            next_btn = self._find_button(["Next", "Next page", "Continue", "Siguiente", "Siguiente página", "Susunod"])
            if next_btn:
                next_btn.scroll_into_view_if_needed()
                next_btn.click()
                self.page.wait_for_load_state("networkidle")
                self.page.wait_for_timeout(1000)
                page_number += 1
            else:
                break

    def detect_form_details_on_page(self):
        """Helper to scrape form details on the current visible page (used in Phase 2)."""
        try:
            self.page.wait_for_selector('div[role="listitem"]', timeout=self.default_timeout)
        except Exception:
            pass

        form_title = "Google Form"
        title_el = self.page.query_selector('h1, div[role="heading"][aria-level="1"], .F9ypgc')
        if title_el:
            form_title = re.sub(r'\s+', ' ', title_el.inner_text()).strip()

        questions = []
        containers = self.page.query_selector_all('div[role="listitem"]')
        
        for container in containers:
            title_el = container.query_selector('div[role="heading"]')
            if not title_el:
                title_el = container.query_selector('.M7eMe')
            if not title_el:
                continue
                
            title_text = re.sub(r'\s+', ' ', title_el.inner_text()).strip()
            
            is_required = False
            if "*" in title_text:
                is_required = True
                title_text = re.sub(r'\s*\*$', '', title_text).strip()
                
            required_input = container.query_selector('[aria-required="true"]')
            if required_input:
                is_required = True

            field_type = None
            options = []
            
            checkboxes = container.query_selector_all('div[role="checkbox"]')
            radios = container.query_selector_all('div[role="radio"]')
            listbox = container.query_selector('div[role="listbox"]')
            textarea = container.query_selector('textarea')
            text_input = container.query_selector('input[type="text"]')

            if checkboxes:
                field_type = "checkbox"
                for cb in checkboxes:
                    label = cb.get_attribute("aria-label") or cb.inner_text() or cb.evaluate("el => el.parentElement.innerText") or ""
                    options.append(re.sub(r'\s+', ' ', label).strip())
            elif radios:
                field_type = "multiple_choice"
                for rd in radios:
                    label = rd.get_attribute("aria-label") or rd.inner_text() or rd.evaluate("el => el.parentElement.innerText") or ""
                    options.append(re.sub(r'\s+', ' ', label).strip())
            elif listbox:
                field_type = "dropdown"
            elif textarea:
                field_type = "paragraph"
            elif text_input:
                field_type = "short_answer"
            else:
                textbox = container.query_selector('div[role="textbox"]')
                if textbox:
                    if textbox.get_attribute("aria-multiline") == "true":
                        field_type = "paragraph"
                    else:
                        field_type = "short_answer"
            
            if field_type:
                questions.append({
                    "title": title_text,
                    "type": field_type,
                    "required": is_required,
                    "options": options
                })

        # Scan for email inputs outside standard listitems in Phase 2
        try:
            email_inputs = self.page.query_selector_all('input[type="email"]')
            for email_in in email_inputs:
                already_scanned = False
                for q in questions:
                    if "email" in q["title"].lower() or "e-mail" in q["title"].lower() or "gmail" in q["title"].lower():
                        already_scanned = True
                        break
                
                if not already_scanned:
                    label_text = "Email Address"
                    aria_label = email_in.get_attribute("aria-label")
                    if aria_label:
                        label_text = re.sub(r'\s+', ' ', aria_label).strip()
                    
                    is_req = email_in.get_attribute("required") is not None or email_in.get_attribute("aria-required") == "true" or True
                    questions.insert(0, {
                        "title": label_text,
                        "type": "email",
                        "required": is_req,
                        "options": []
                    })
        except Exception:
            pass

        # Scan for text inputs that act as email inputs in Phase 2
        try:
            text_inputs = self.page.query_selector_all('input[type="text"]')
            for txt_in in text_inputs:
                aria_label = txt_in.get_attribute("aria-label") or ""
                autocomplete = txt_in.get_attribute("autocomplete") or ""
                placeholder = txt_in.get_attribute("placeholder") or ""
                
                is_email = False
                if any(kw in aria_label.lower() for kw in ["email", "e-mail", "gmail"]):
                    is_email = True
                elif any(kw in autocomplete.lower() for kw in ["email"]):
                    is_email = True
                elif any(kw in placeholder.lower() for kw in ["email"]):
                    is_email = True
                    
                if is_email:
                    label_name = aria_label if aria_label else "Email Address"
                    label_name = re.sub(r'\s+', ' ', label_name).strip()
                    
                    already_scanned = False
                    for q in questions:
                        if q["title"].lower() == label_name.lower() or "email" in q["title"].lower():
                            already_scanned = True
                            break
                            
                    if not already_scanned:
                        is_req = txt_in.get_attribute("required") is not None or txt_in.get_attribute("aria-required") == "true" or True
                        questions.insert(0, {
                            "title": label_name,
                            "type": "email",
                            "required": is_req,
                            "options": []
                        })
        except Exception:
            pass
                
        return form_title, questions

    # ==========================================
    # CORE INTERACTIONS & OPTION MATCHING
    # ==========================================
    def _fill_single_field(self, q_title, value):
        """Helper to fill a single field inside its specific question container using a Tiered Search Strategy."""
        q_title_clean = re.sub(r'\s+', ' ', q_title).strip()
        
        # Tiered Container Locating Strategy
        container_loc = None
        
        # Tier 1: Full text match (ignoring whitespace)
        loc = self.page.locator('div[role="listitem"]').filter(has_text=q_title_clean).first
        if loc.count() > 0:
            container_loc = loc
            
        # Tier 2: Match the part before any parentheses (e.g. "Name (Last name...)" -> "Name")
        if not container_loc and "(" in q_title_clean:
            prefix = q_title_clean.split("(")[0].strip()
            if len(prefix) >= 3:
                loc = self.page.locator('div[role="listitem"]').filter(has_text=prefix).first
                if loc.count() > 0:
                    container_loc = loc
                    if self.logger:
                        self.logger.info(f"Located container using parenthesis prefix: '{prefix}'")

        # Tier 3: Match by first 15 characters
        if not container_loc and len(q_title_clean) > 15:
            short_prefix = q_title_clean[:15].strip()
            loc = self.page.locator('div[role="listitem"]').filter(has_text=short_prefix).first
            if loc.count() > 0:
                container_loc = loc
                if self.logger:
                    self.logger.info(f"Located container using short prefix: '{short_prefix}'")

        if not container_loc:
            # Fallback for email fields that are outside standard listitem containers
            if any(kw in q_title_clean.lower() for kw in ["email", "e-mail", "gmail"]):
                for selector in ['input[type="email"]', 'input[autocomplete="email"]', 'input[aria-label*="email" i]', 'input[aria-label*="e-mail" i]', 'input[placeholder*="email" i]']:
                    try:
                        loc = self.page.locator(selector).first
                        if loc.count() > 0:
                            loc.scroll_into_view_if_needed()
                            loc.click()
                            self.page.wait_for_timeout(50)
                            loc.fill(str(value))
                            if self.logger:
                                self.logger.info(f"Filled email field via global selector: '{selector}' with '{value}'")
                            return
                    except Exception:
                        continue
            
            if self.logger:
                self.logger.warning(f"Could not locate container for question: '{q_title_clean}'")
            return

        container_loc.scroll_into_view_if_needed()
        self.page.wait_for_timeout(50)

        # 1. Text Fields (Name, Email, Student ID, etc.)
        text_input = self._find_text_input(container_loc)
        if text_input:
            try:
                text_input.click()
                self.page.wait_for_timeout(50)
                text_input.fill(str(value))
            except Exception:
                text_input.type(str(value))
            if self.logger:
                self.logger.info(f"Successfully filled text field with: '{value}'")
            return

        # 2. Checkboxes
        checkboxes_loc = container_loc.locator('div[role="checkbox"]')
        if checkboxes_loc.count() > 0:
            if isinstance(value, list):
                target_vals = [str(v).strip() for v in value]
            else:
                target_vals = [v.strip() for v in str(value).split(",") if v.strip()]

            checkboxes = checkboxes_loc.all()
            available_options = []
            for cb in checkboxes:
                label = cb.get_attribute("aria-label") or cb.inner_text() or cb.evaluate("el => el.parentElement.innerText") or ""
                available_options.append(re.sub(r'\s+', ' ', label).strip())

            for tv in target_vals:
                matched_opt = self._match_option_value(tv, available_options)
                if matched_opt:
                    for cb in checkboxes:
                        label = cb.get_attribute("aria-label") or cb.inner_text() or cb.evaluate("el => el.parentElement.innerText") or ""
                        if re.sub(r'\s+', ' ', label).strip() == matched_opt:
                            checked_state = cb.get_attribute("aria-checked")
                            if checked_state != "true":
                                cb.click()
            return

        # 3. Multiple Choice (Radio)
        radios_loc = container_loc.locator('div[role="radio"]')
        if radios_loc.count() > 0:
            radios = radios_loc.all()
            available_options = []
            for rd in radios:
                label = rd.get_attribute("aria-label") or rd.inner_text() or rd.evaluate("el => el.parentElement.innerText") or ""
                available_options.append(re.sub(r'\s+', ' ', label).strip())

            matched_opt = self._match_option_value(str(value), available_options)
            if matched_opt:
                for rd in radios:
                    label = rd.get_attribute("aria-label") or rd.inner_text() or rd.evaluate("el => el.parentElement.innerText") or ""
                    if re.sub(r'\s+', ' ', label).strip() == matched_opt:
                        rd.click()
                        break
            return

        # 4. Dropdown
        listbox_loc = container_loc.locator('div[role="listbox"]')
        if listbox_loc.count() > 0:
            listbox_el = listbox_loc.first
            listbox_el.click()
            self.page.wait_for_timeout(400)
            
            try:
                self.page.wait_for_selector('div[role="option"]', timeout=3000)
                options = self.page.locator('div[role="option"]').all()
                available_options = []
                for opt in options:
                    if opt.is_visible():
                        label = opt.get_attribute("data-value") or opt.inner_text() or ""
                        available_options.append(re.sub(r'\s+', ' ', label).strip())

                matched_opt = self._match_option_value(str(value), available_options)
                if matched_opt:
                    for opt in options:
                        if opt.is_visible():
                            label = opt.get_attribute("data-value") or opt.inner_text() or ""
                            if re.sub(r'\s+', ' ', label).strip() == matched_opt:
                                opt.click()
                                return
                self.page.keyboard.press("Escape")
            except Exception:
                self.page.keyboard.press("Escape")
            return

        # 5. Date / Time (fallback)
        date_input_loc = container_loc.locator('input[type="date"]')
        if date_input_loc.count() > 0:
            date_input_loc.first.fill(str(value))
            return
            
        time_input_loc = container_loc.locator('input[type="time"]')
        if time_input_loc.count() > 0:
            time_input_loc.first.fill(str(value))
            return

    def _find_text_input(self, container_loc):
        """Finds the first valid text input element inside the container."""
        for selector in ['input[type="text"]', 'textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
            loc = container_loc.locator(selector).first
            if loc.count() > 0:
                return loc
        return None

    def _find_button(self, text_list):
        """Helper to find a button by its text content."""
        for text in text_list:
            selectors = [
                f'div[role="button"]:has-text("{text}")',
                f'span:has-text("{text}")',
                f'text={text}',
                f'div[role="button"] >> text={text}'
            ]
            for selector in selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn_text = btn.inner_text().strip().lower()
                        if any(t.lower() in btn_text for t in text_list):
                            return btn
                except Exception:
                    continue
        return None

    def _match_option_value(self, value, options):
        """Finds the best option that matches the value using a prioritized matching strategy."""
        val_clean = str(value).strip().lower()
        if not val_clean:
            return None

        # 1. Exact match (case-insensitive)
        for opt in options:
            if opt.strip().lower() == val_clean:
                return opt

        # 2. Partial contains match
        for opt in options:
            if val_clean in opt.strip().lower() or opt.strip().lower() in val_clean:
                return opt

        # 3. Number-aware match (e.g. "21" matches "21 years old and above")
        val_numbers = re.findall(r'\d+', val_clean)
        if val_numbers:
            for opt in options:
                opt_numbers = re.findall(r'\d+', opt.lower())
                if opt_numbers and val_numbers[0] == opt_numbers[0]:
                    return opt

        # 4. Fuzzy match with SequenceMatcher
        best_score = 0
        best_opt = None
        for opt in options:
            score = SequenceMatcher(None, val_clean, opt.strip().lower()).ratio()
            if score >= 0.6 and score > best_score:
                best_score = score
                best_opt = opt
        if best_opt:
            return best_opt

        return None

    def submit_form(self):
        """Attempts to submit the Google Form."""
        if not self.page:
            raise Exception("Browser page is not loaded.")

        if self.logger:
            self.logger.info("Attempting to submit form...")

        submit_selectors = [
            'div[role="button"]:has-text("Submit")',
            'span:has-text("Submit")',
            'text=Submit',
            'div[role="button"] >> text=Submit',
            'div[role="button"]:has-text("Isumite")',
            'span:has-text("Isumite")',
            'text=Isumite'
        ]

        submitted = False
        for selector in submit_selectors:
            try:
                btn = self.page.locator(selector).first
                if btn.count() > 0 and btn.is_visible():
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            try:
                submit_btn = self.page.locator('input[type="submit"], button[type="submit"]').first
                if submit_btn.count() > 0:
                    submit_btn.click()
                    submitted = True
            except Exception as e:
                raise Exception(f"Could not find or click Submit button. Error: {e}")

        self.page.wait_for_load_state("networkidle")

    def is_submitted(self):
        """Checks if the form was successfully submitted by inspecting the page content."""
        if not self.page:
            return False

        success_indicators = [
            "Your response has been recorded.",
            "Submit another response",
            "has been recorded",
            "response was submitted"
        ]

        for indicator in success_indicators:
            try:
                if self.page.locator(f'text={indicator}').count() > 0:
                    return True
            except Exception:
                continue
        return False

    def reload_form(self, url):
        """Reloads the form."""
        self.navigate_to_form(url)
