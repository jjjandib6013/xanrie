import threading
import json
import os
import customtkinter as ctk
from tkinter import messagebox

from browser import BrowserController
from parser import FormParser
from form_mapper import FormMapper
from template_manager import TemplateManager
from logger import SubmissionLogger
import synthetic_generator

# Set appearance and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class XanrieApp(ctk.CTk):
    def __init__(self, config_path="config.json"):
        super().__init__()

        # Load config
        self.config_path = config_path
        self.config = self.load_config()

        # Initialize core components
        self.logger = SubmissionLogger()
        self.logger.register_gui_callback(self.log_to_gui)
        
        self.parser = FormParser(global_aliases=self.config.get("aliases"))
        self.mapper = FormMapper(
            fuzzy_threshold=self.config.get("fuzzy_match_threshold", 0.75),
            global_aliases=self.config.get("aliases")
        )
        self.template_manager = TemplateManager()
        self.browser_controller = None

        # Threading and control states
        self.worker_thread = None
        self.is_running_automation = False
        
        # Scanned form state
        self.scanned_url = None
        self.detected_title = "None"
        self.detected_questions = []
        self.current_template = None

        # Configure window
        self.title("Xanrie Forms Automator")
        self.geometry("1150x750")
        self.minsize(1000, 650)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Build GUI Layout
        self.setup_layout()
        
        # Initial logs
        self.logger.info("Application initialized. Ready to automate.")

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "auto_submit": False, 
            "default_timeout": 15000, 
            "fuzzy_match_threshold": 0.75, 
            "aliases": {},
            "dummy_data": {}
        }

    def setup_layout(self):
        # 2-column Grid Layout
        self.grid_columnconfigure(0, weight=4, minsize=450) # Left panel (Inputs/Controls)
        self.grid_columnconfigure(1, weight=5, minsize=500) # Right panel (Status/Logs)
        self.grid_rowconfigure(0, weight=1)

        # ------------------ LEFT PANEL ------------------
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(2, weight=1) # Raw text textbox gets the space

        # Header
        header_label = ctk.CTkLabel(
            left_panel, 
            text="Xanrie", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        header_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 10))

        # Form URL Input
        url_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        url_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        url_frame.grid_columnconfigure(0, weight=1)
        
        url_label = ctk.CTkLabel(url_frame, text="Google Form URL:", font=ctk.CTkFont(weight="bold"))
        url_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        self.url_entry = ctk.CTkEntry(
            url_frame, 
            placeholder_text="https://docs.google.com/forms/d/e/.../viewform"
        )
        self.url_entry.grid(row=1, column=0, sticky="ew")

        # Raw Text Input
        raw_text_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        raw_text_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
        raw_text_frame.grid_columnconfigure(0, weight=1)
        raw_text_frame.grid_rowconfigure(1, weight=1)

        raw_text_label = ctk.CTkLabel(raw_text_frame, text="Raw Text Data (Fill the template generated after scanning):", font=ctk.CTkFont(weight="bold"))
        raw_text_label.grid(row=0, column=0, sticky="w", pady=(0, 2))

        self.raw_textbox = ctk.CTkTextbox(raw_text_frame, wrap="word")
        self.raw_textbox.grid(row=1, column=0, sticky="nsew")

        # Toggles Frame
        toggles_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        toggles_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=10)
        toggles_frame.grid_columnconfigure((0, 1), weight=1)
        
        self.auto_submit_switch = ctk.CTkSwitch(
            toggles_frame, 
            text="Auto-Submit", 
            onvalue=True, 
            offvalue=False
        )
        self.auto_submit_switch.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        if self.config.get("auto_submit", False):
            self.auto_submit_switch.select()

        self.dummy_data_switch = ctk.CTkSwitch(
            toggles_frame, 
            text="Use Dummy Data for Missing Fields", 
            onvalue=True, 
            offvalue=False
        )
        self.dummy_data_switch.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.dummy_data_switch.select()

        # Synthetic Data Generation Frame
        synthetic_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        synthetic_frame.grid(row=4, column=0, sticky="ew", padx=15, pady=10)
        synthetic_frame.grid_columnconfigure(0, weight=1)
        synthetic_frame.grid_columnconfigure(1, weight=1)

        synth_label = ctk.CTkLabel(synthetic_frame, text="Synthetic Test Records:", font=ctk.CTkFont(weight="bold"))
        synth_label.grid(row=0, column=0, sticky="w", padx=5)

        self.synth_count_combo = ctk.CTkComboBox(synthetic_frame, values=["1", "3", "5", "10", "20", "50"])
        self.synth_count_combo.grid(row=0, column=1, padx=5, sticky="ew")
        self.synth_count_combo.set("5")

        self.generate_synth_btn = ctk.CTkButton(
            synthetic_frame,
            text="Generate Test Data",
            command=self.on_generate_synth_click,
            fg_color="gray30",
            hover_color="gray45",
            state="disabled"
        )
        self.generate_synth_btn.grid(row=1, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="ew")

        # Buttons Grid
        buttons_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        buttons_frame.grid(row=5, column=0, sticky="ew", padx=15, pady=10)
        buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.scan_btn = ctk.CTkButton(
            buttons_frame, 
            text="1. Start Scan", 
            command=self.on_scan_click,
            fg_color="#1c7ed6",
            hover_color="#1864ab",
            font=ctk.CTkFont(weight="bold"),
            height=35
        )
        self.scan_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.fill_btn = ctk.CTkButton(
            buttons_frame, 
            text="2. Start Filling", 
            command=self.on_fill_click,
            fg_color="#2b8a3e",
            hover_color="#2b8a3e",
            font=ctk.CTkFont(weight="bold"),
            height=35,
            state="disabled"
        )
        self.fill_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.submit_btn = ctk.CTkButton(
            buttons_frame, 
            text="Submit Form (Browser)", 
            command=self.on_submit_click,
            fg_color="#e03131",
            hover_color="#c92a2a",
            height=35,
            state="disabled"
        )
        self.submit_btn.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.clear_btn = ctk.CTkButton(
            buttons_frame, 
            text="Clear All", 
            command=self.on_clear_click,
            fg_color="gray30",
            hover_color="gray40",
            height=35
        )
        self.clear_btn.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(left_panel)
        self.progress_bar.grid(row=6, column=0, sticky="ew", padx=20, pady=(5, 15))
        self.progress_bar.set(0)

        # ------------------ RIGHT PANEL ------------------
        right_panel = ctk.CTkFrame(self, corner_radius=0)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=4) # Tabview gets weight
        right_panel.grid_rowconfigure(4, weight=3) # Log box gets weight

        # Header Details
        self.form_title_label = ctk.CTkLabel(
            right_panel, 
            text="Detected Form: None", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#1c7ed6"
        )
        self.form_title_label.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 2))

        self.page_status_label = ctk.CTkLabel(
            right_panel, 
            text="Page Status: Not Started", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f08c00"
        )
        self.page_status_label.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))

        # Tabview for summaries
        self.tabview = ctk.CTkTabview(right_panel)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=15, pady=5)
        self.tabview.add("Scanned Structure")
        self.tabview.add("Parsed Preview")

        # Tab 1: Scanned Structure
        tab_summary = self.tabview.tab("Scanned Structure")
        tab_summary.grid_columnconfigure(0, weight=1)
        tab_summary.grid_rowconfigure(0, weight=1)
        
        self.summary_textbox = ctk.CTkTextbox(tab_summary, wrap="none")
        self.summary_textbox.grid(row=0, column=0, sticky="nsew")
        self.summary_textbox.configure(state="disabled")

        # Tab 2: Parsed Preview
        tab_parsed = self.tabview.tab("Parsed Preview")
        tab_parsed.grid_columnconfigure(0, weight=1)
        tab_parsed.grid_rowconfigure(0, weight=1)
        
        self.parsed_textbox = ctk.CTkTextbox(tab_parsed, wrap="none")
        self.parsed_textbox.grid(row=0, column=0, sticky="nsew")
        self.parsed_textbox.configure(state="disabled")

        # Scrolling Status Log Header
        log_header = ctk.CTkLabel(right_panel, text="Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_header.grid(row=3, column=0, sticky="w", padx=15, pady=(10, 2))

        # Scrolling Status Log Textbox
        self.log_textbox = ctk.CTkTextbox(right_panel, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.grid(row=4, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_textbox.configure(state="disabled")

    # ------------------ THREAD-SAFE GUI UPDATERS ------------------
    def run_on_main_thread(self, fn, *args, **kwargs):
        """Schedules a function to run safely on the Tkinter main thread."""
        self.after(0, lambda: fn(*args, **kwargs))

    def log_to_gui(self, log_message):
        """Callback registered with the logger to stream messages in real-time."""
        self.run_on_main_thread(self._append_log_text, log_message)

    def _append_log_text(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def update_progress(self, current, total):
        self.run_on_main_thread(self._set_progress, current / total)

    def _set_progress(self, fraction):
        self.progress_bar.set(fraction)

    def set_form_title(self, title):
        self.run_on_main_thread(self.form_title_label.configure, text=f"Detected Form: {title}")

    def update_page_status(self, page_num, status):
        self.run_on_main_thread(
            self.page_status_label.configure, 
            text=f"Page Status: {status} (Page {page_num})"
        )

    def update_status_panels(self, parsed_json, summary_text):
        self.run_on_main_thread(self._update_status_panels, parsed_json, summary_text)

    def _update_status_panels(self, parsed_json, summary_text):
        self.parsed_textbox.configure(state="normal")
        self.parsed_textbox.delete("1.0", "end")
        self.parsed_textbox.insert("1.0", parsed_json)
        self.parsed_textbox.configure(state="disabled")

        self.summary_textbox.configure(state="normal")
        self.summary_textbox.delete("1.0", "end")
        self.summary_textbox.insert("1.0", summary_text)
        self.summary_textbox.configure(state="disabled")

    def populate_template_in_textbox(self, template_text):
        self.run_on_main_thread(self._populate_template_in_textbox, template_text)

    def _populate_template_in_textbox(self, template_text):
        current_val = self.raw_textbox.get("1.0", "end-1c").strip()
        if not current_val:
            self.raw_textbox.delete("1.0", "end")
            self.raw_textbox.insert("1.0", template_text)
            self.logger.info("Generated raw data template in the textbox.")

    # ------------------ EVENT HANDLERS ------------------
    def on_clear_click(self):
        self.url_entry.delete(0, "end")
        self.raw_textbox.delete("1.0", "end")
        
        self.summary_textbox.configure(state="normal")
        self.summary_textbox.delete("1.0", "end")
        self.summary_textbox.configure(state="disabled")
        
        self.parsed_textbox.configure(state="normal")
        self.parsed_textbox.delete("1.0", "end")
        self.parsed_textbox.configure(state="disabled")
        
        self.form_title_label.configure(text="Detected Form: None")
        self.page_status_label.configure(text="Page Status: Not Started")
        self.progress_bar.set(0)
        self.fill_btn.configure(state="disabled")
        self.submit_btn.configure(state="disabled")
        self.generate_synth_btn.configure(state="disabled")
        self.preview_synth_btn.configure(state="disabled")
        self.use_synth_btn.configure(state="disabled")
        
        self.city_combo.set("Random")
        self.brgy_combo.configure(values=["Random"])
        self.brgy_combo.set("Random")
        self.synth_count_combo.set("5")
        
        self.scanned_url = None
        self.detected_title = "None"
        self.detected_questions = []
        self.current_template = None
        
        self.logger.info("Cleared all fields.")

    def on_submit_click(self):
        """Triggers manual form submission via background thread."""
        if not self.browser_controller or not self.browser_controller.page:
            messagebox.showerror("Error", "No browser window is currently open.")
            return
            
        self.submit_btn.configure(state="disabled")
        threading.Thread(target=self._async_submit, daemon=True).start()

    def _async_submit(self):
        try:
            self.logger.info("Submitting form...")
            self.browser_controller.submit_form()
            if self.browser_controller.is_submitted():
                self.logger.info("Form submitted successfully!")
                self.run_on_main_thread(messagebox.showinfo, "Success", "Form submitted successfully!")
            else:
                self.logger.warning("Form submitted, but could not verify confirmation page.")
        except Exception as e:
            self.logger.error(f"Form submission failed: {e}")
            self.run_on_main_thread(messagebox.showerror, "Submission Error", f"Failed to submit: {e}")

    # --- PHASE 1: START SCAN ---
    def on_scan_click(self):
        if self.is_running_automation:
            messagebox.showwarning("Running", "An automation task is already running.")
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid Google Form URL to scan.")
            return

        self.is_running_automation = True
        self.scan_btn.configure(state="disabled")
        self.fill_btn.configure(state="disabled")
        self.submit_btn.configure(state="disabled")

        threading.Thread(target=self._run_scan_worker, args=(url,), daemon=True).start()

    def _run_scan_worker(self, url):
        try:
            # Safely close any existing browser controller to avoid thread conflicts
            if self.browser_controller:
                try:
                    self.browser_controller.close_browser()
                except Exception:
                    pass
            
            self.browser_controller = BrowserController(
                default_timeout=self.config.get("default_timeout", 15000),
                logger=self.logger
            )

            # Start scan
            form_title, questions = self.browser_controller.scan_entire_form(
                url=url,
                config_dummy_data=self.config.get("dummy_data", {})
            )
            
            self.scanned_url = url
            self.detected_title = form_title
            self.detected_questions = questions

            self.set_form_title(form_title)
            self.update_page_status(len(questions), "Scan Complete")

            # Automatically generate synthetic data instead of a blank template
            try:
                count = int(self.synth_count_combo.get().strip())
            except ValueError:
                count = 5
            
            city = self.city_combo.get()
            brgy = self.brgy_combo.get()
            use_localized = self.use_localized_switch.get()
            vary_likert = self.vary_likert_switch.get()

            self.logger.info(f"Auto-generating {count} synthetic Cebu-localized test records based on scanned structure...")
            synthetic_data = synthetic_generator.generate_batch_synthetic_data(
                questions, count, city, brgy, use_localized, vary_likert
            )
            self.run_on_main_thread(self._populate_synthetic_data, synthetic_data)

            # Build structural JSON report to display in tab
            structure_report = []
            structure_report.append(f"Form Title: {form_title}")
            structure_report.append(f"Total Questions: {len(questions)}")
            structure_report.append("\n=== QUESTIONS STRUCTURE ===")
            for idx, q in enumerate(questions):
                structure_report.append(f"{idx+1}. {q['label']}")
                structure_report.append(f"   - Type: {q['type']}")
                structure_report.append(f"   - Required: {q['required']}")
                if q["options"]:
                    structure_report.append(f"   - Options: {q['options']}")
                if q["dummy_answer"]:
                    structure_report.append(f"   - Dummy Plan: {q['dummy_answer']}")
                structure_report.append("")
                
            self.update_status_panels("{}", "\n".join(structure_report))

            # Enable Fill and all Synthetic buttons
            self.run_on_main_thread(self.fill_btn.configure, state="normal")
            self.run_on_main_thread(self.generate_synth_btn.configure, state="normal")
            self.run_on_main_thread(self.preview_synth_btn.configure, state="normal")
            self.run_on_main_thread(self.use_synth_btn.configure, state="normal")
            self.run_on_main_thread(
                messagebox.showinfo, 
                "Scan Complete", 
                f"Form scanned successfully! {count} Cebu-localized synthetic records have been generated in the textbox. Click '2. Start Filling' to begin automation."
            )

        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            self.run_on_main_thread(messagebox.showerror, "Scan Error", f"Failed to scan form: {e}")
        finally:
            self.is_running_automation = False
            self.run_on_main_thread(self.scan_btn.configure, state="normal")

    def _populate_synthetic_data(self, text):
        self.raw_textbox.delete("1.0", "end")
        self.raw_textbox.insert("1.0", text)

    def update_barangay_list(self, choice):
        if choice == "Random":
            self.brgy_combo.configure(values=["Random"])
            self.brgy_combo.set("Random")
        else:
            city_data = synthetic_generator.CEBU_DATASET.get(choice)
            if city_data:
                brgys = ["Random"] + city_data["sample_barangays"]
                self.brgy_combo.configure(values=brgys)
                self.brgy_combo.set("Random")

    def on_generate_synth_click(self):
        if not self.detected_questions:
            messagebox.showwarning("Warning", "Please scan a form first.")
            return
            
        try:
            count = int(self.synth_count_combo.get().strip())
        except ValueError:
            count = 5
            
        city = self.city_combo.get()
        brgy = self.brgy_combo.get()
        use_localized = self.use_localized_switch.get()
        vary_likert = self.vary_likert_switch.get()
        
        self.logger.info(f"Generating {count} Cebu-localized synthetic test records...")
        synthetic_data = synthetic_generator.generate_batch_synthetic_data(
            self.detected_questions, count, city, brgy, use_localized, vary_likert
        )
        
        self._populate_synthetic_data(synthetic_data)
        self.logger.info("Synthetic raw text populated successfully.")

    def on_preview_synth_click(self):
        if not self.detected_questions:
            messagebox.showwarning("Warning", "Please scan a form first.")
            return
            
        try:
            count = int(self.synth_count_combo.get().strip())
        except ValueError:
            count = 5
            
        city = self.city_combo.get()
        brgy = self.brgy_combo.get()
        use_localized = self.use_localized_switch.get()
        vary_likert = self.vary_likert_switch.get()
        
        self.logger.info("Generating data preview...")
        synthetic_data = synthetic_generator.generate_batch_synthetic_data(
            self.detected_questions, count, city, brgy, use_localized, vary_likert
        )
        
        records_text = self.parser.split_records(synthetic_data)
        preview_list = []
        for i, rec_text in enumerate(records_text):
            parsed = self.parser.parse_record(rec_text)
            preview_list.append(f"--- Record {i+1} Preview ---\n{json.dumps(parsed, indent=2)}")
            
        preview_text = "\n\n".join(preview_list)
        self.run_on_main_thread(self._update_parsed_preview, preview_text)
        self.run_on_main_thread(self.tabview.set, "Parsed Preview")
        self.logger.info("Preview loaded in 'Parsed Preview' tab.")

    def on_use_synth_click(self):
        self.on_generate_synth_click()
        self.on_fill_click()

    # --- PHASE 2: START FILLING ---
    def on_fill_click(self):
        if self.is_running_automation:
            messagebox.showwarning("Running", "An automation task is already running.")
            return

        url = self.url_entry.get().strip()
        raw_text = self.raw_textbox.get("1.0", "end-1c").strip()

        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid Google Form URL.")
            return
        if not raw_text:
            messagebox.showwarning("Missing Data", "Please enter raw text data to fill.")
            return

        self.is_running_automation = True
        self.scan_btn.configure(state="disabled")
        self.fill_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.submit_btn.configure(state="disabled")
        
        self.worker_thread = threading.Thread(
            target=self._run_fill_worker, 
            args=(url, raw_text), 
            daemon=True
        )
        self.worker_thread.start()

    def _run_fill_worker(self, url, raw_text):
        try:
            # Safely close any existing browser controller to avoid thread conflicts
            if self.browser_controller:
                try:
                    self.browser_controller.close_browser()
                except Exception:
                    pass
            
            self.browser_controller = BrowserController(
                default_timeout=self.config.get("default_timeout", 15000),
                logger=self.logger
            )

            # Split raw text into records
            records_text = self.parser.split_records(raw_text)
            total_records = len(records_text)
            
            if total_records == 0:
                self.logger.error("No valid records found in raw data.")
                return

            self.logger.info(f"Detected {total_records} record(s) to process.")

            auto_submit = self.auto_submit_switch.get()

            for i, record_text in enumerate(records_text):
                record_num = i + 1
                self.logger.info(f"=== Processing Record {record_num}/{total_records} ===")
                
                # Parse single record
                parsed_record = self.parser.parse_record(record_text)
                parsed_json = json.dumps(parsed_record, indent=2)
                self.run_on_main_thread(self._update_parsed_preview, f"Record {record_num}/{total_records}:\n{parsed_json}")

                # Ensure browser is on the form page
                self.logger.info(f"Loading/reloading form for Record {record_num}...")
                self.browser_controller.navigate_to_form(url)

                self.logger.info(f"Filling Form for Record {record_num}...")
                self.browser_controller.fill_form_with_real_data(
                    mapper=self.mapper,
                    parsed_record=parsed_record,
                    template=self.current_template,
                    use_dummy_data=self.dummy_data_switch.get(),
                    config_dummy_data=self.config.get("dummy_data", {}),
                    progress_callback=self.update_progress
                )

                if auto_submit:
                    self.logger.info(f"Submitting Record {record_num}...")
                    self.browser_controller.submit_form()
                    if self.browser_controller.is_submitted():
                        self.logger.info(f"Record {record_num} submitted successfully!")
                    else:
                        self.logger.warning(f"Record {record_num} submitted, confirmation page not verified.")
                    self.page_status_label.configure(text=f"Record {record_num}/{total_records} Submitted")
                else:
                    # If auto_submit is off, we pause and wait for the user to review/submit this record.
                    self.logger.info(f"Record {record_num} filled. Waiting for you to review and submit in the browser.")
                    self.run_on_main_thread(self.submit_btn.configure, state="normal")
                    
                    # If it's not the last record, prompt user to continue when ready
                    if record_num < total_records:
                        self.run_on_main_thread(
                            messagebox.showinfo, 
                            "Review & Submit", 
                            f"Record {record_num} is filled. Please verify/submit it in the browser, then click OK here to load and fill Record {record_num+1}."
                        )
                    else:
                        self.run_on_main_thread(
                            messagebox.showinfo, 
                            "Filling Complete", 
                            "Final record filled! Please submit manually in the browser."
                        )

            if auto_submit:
                self.logger.info("All records processed successfully!")
                self.run_on_main_thread(messagebox.showinfo, "Automation Complete", f"Successfully completed all {total_records} submissions!")

        except Exception as e:
            self.logger.error(f"Filling failed: {e}")
            self.run_on_main_thread(messagebox.showerror, "Error", f"Filling failed: {e}")
        finally:
            self.is_running_automation = False
            self.run_on_main_thread(self._reset_button_states)

    def _update_parsed_preview(self, parsed_json):
        self.parsed_textbox.configure(state="normal")
        self.parsed_textbox.delete("1.0", "end")
        self.parsed_textbox.insert("1.0", parsed_json)
        self.parsed_textbox.configure(state="disabled")

    def _reset_button_states(self):
        self.scan_btn.configure(state="normal")
        self.fill_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")

    def on_closing(self):
        """Handle window closing to clean up browser processes."""
        if self.browser_controller:
            try:
                self.browser_controller.close_browser()
            except Exception:
                pass
        self.destroy()
