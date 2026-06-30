import os
import datetime
import logging

class SubmissionLogger:
    def __init__(self, log_dir="logs", log_file="submissions.log"):
        self.log_dir = log_dir
        self.log_path = os.path.join(log_dir, log_file)
        self.callbacks = []
        
        # Ensure log directory exists
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
            
        # Set up standard logger
        self.logger = logging.getLogger("GoogleFormAutomation")
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            # File handler
            file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Stream handler (console)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def register_gui_callback(self, callback):
        """Register a callback to receive log messages in real-time (e.g., for GUI updates)."""
        self.callbacks.append(callback)

    def _log(self, level, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        
        # Call standard logger
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
            
        # Notify GUI callbacks
        for callback in self.callbacks:
            try:
                callback(log_msg)
            except Exception:
                pass

    def info(self, message):
        self._log("INFO", message)

    def warning(self, message):
        self._log("WARNING", message)

    def error(self, message):
        self._log("ERROR", message)

    def log_submission(self, form_title, form_id_or_url, record_idx, fields_filled, unmapped, missing_required, status, error_details=None):
        msg = (
            f"Submission Event:\n"
            f"  Form Title: {form_title}\n"
            f"  Form ID/URL: {form_id_or_url}\n"
            f"  Record Index: {record_idx if record_idx is not None else 'N/A'}\n"
            f"  Status: {status}\n"
            f"  Fields Filled: {fields_filled}\n"
            f"  Unmapped Keys: {unmapped}\n"
            f"  Missing Required Fields: {missing_required}\n"
        )
        if error_details:
            msg += f"  Error Details: {error_details}\n"
        
        if status == "SUCCESS":
            self.info(msg)
        else:
            self.error(msg)
