import os
import json
from gui import GoogleFormAutomationApp
from template_manager import TemplateManager

def ensure_directories():
    """Ensure that the templates and logs directories exist."""
    directories = ["templates", "logs"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

def create_default_config():
    """Creates a default config.json if it doesn't exist."""
    config_path = "config.json"
    if not os.path.exists(config_path):
        default_config = {
            "auto_submit": False,
            "default_timeout": 15000,
            "fuzzy_match_threshold": 0.75,
            "max_retries": 3,
            "aliases": {
                "student no": "student id",
                "id number": "student id",
                "full name": "name",
                "email address": "email",
                "course name": "course",
                "class section": "section",
                "notes": "remarks",
                "comments": "remarks"
            }
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def main():
    ensure_directories()
    create_default_config()
    
    # Create the sample template if not already present
    tm = TemplateManager()
    tm.create_sample_template()
    
    # Start the GUI
    app = GoogleFormAutomationApp()
    app.mainloop()

if __name__ == "__main__":
    main()
