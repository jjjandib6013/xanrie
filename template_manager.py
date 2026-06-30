import os
import json
import re

class TemplateManager:
    def __init__(self, templates_dir="templates"):
        self.templates_dir = templates_dir
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)
            
    def extract_form_id(self, url):
        """Extracts the unique form ID from a Google Form URL."""
        if not url:
            return None
        match = re.search(r'/forms/d/(e/)?([^/]+)', url)
        if match:
            return match.group(2)
        return None

    def get_template(self, url=None, form_title=None):
        """Attempts to find and load a template by form ID (from URL) or form title.
        Returns the template dict if found, otherwise None.
        """
        form_id = self.extract_form_id(url)
        
        # 1. Try loading by form_id
        if form_id:
            filename = f"{form_id}.json"
            filepath = os.path.join(self.templates_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass

        # 2. If not found, search all templates in the directory for a matching form_id or form_title
        if os.path.exists(self.templates_dir):
            for file in os.listdir(self.templates_dir):
                if file.endswith(".json"):
                    filepath = os.path.join(self.templates_dir, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            template = json.load(f)
                            if form_id and template.get("form_id") == form_id:
                                return template
                            if form_title and template.get("form_title", "").lower().strip() == form_title.lower().strip():
                                return template
                    except Exception:
                        continue
                        
        return None

    def save_template(self, url, form_title, mappings):
        """Saves a template to a JSON file.
        Uses the form ID as the filename, or a sanitized form title if ID is not found.
        """
        form_id = self.extract_form_id(url)
        if not form_id and not form_title:
            return False
            
        filename = f"{form_id}.json" if form_id else f"title_{self._sanitize_filename(form_title)}.json"
        filepath = os.path.join(self.templates_dir, filename)
        
        template_data = {
            "form_id": form_id or "",
            "form_title": form_title or "",
            "mappings": mappings
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _sanitize_filename(self, name):
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

    def create_sample_template(self):
        """Creates an example template file as requested."""
        sample = {
            "form_id": "sample_form_id",
            "form_title": "Student Attendance Form",
            "mappings": {
              "Full Name": {
                "input_key": "Name",
                "type": "short_answer",
                "required": True,
                "aliases": ["name", "full name", "student name"]
              },
              "Student ID Number": {
                "input_key": "Student ID",
                "type": "short_answer",
                "required": True,
                "aliases": ["student no", "id number", "student number"]
              },
              "Remarks": {
                "input_key": "Remarks",
                "type": "paragraph",
                "required": False,
                "aliases": ["notes", "comments", "remarks"]
              }
            }
          }
        filepath = os.path.join(self.templates_dir, "sample_form_template.json")
        if not os.path.exists(filepath):
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(sample, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
