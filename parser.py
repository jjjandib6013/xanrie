import re

class FormParser:
    def __init__(self, global_aliases=None):
        # Store lowercase aliases for case-insensitive lookup
        self.global_aliases = {}
        if global_aliases:
            for alias, standard_key in global_aliases.items():
                self.global_aliases[alias.lower().strip()] = standard_key

    def split_records(self, raw_text):
        """Splits the raw text into multiple records based on '---' delimiter.
        If no '---' is found, returns the whole text as a single record.
        """
        raw_text = raw_text.strip()
        if not raw_text:
            return []

        # Split by '---'
        if "---" in raw_text:
            records = re.split(r'\n?\s*---\s*\n?', raw_text)
            # Filter out empty records
            return [r.strip() for r in records if r.strip()]
        
        return [raw_text]

    def parse_record(self, record_text):
        """Parses a single record string into a dictionary of key-value pairs.
        Supports separators: ':', '=', '-'
        Handles inconsistent spacing and casing.
        """
        parsed_data = {}
        lines = record_text.splitlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            matched = False
            # Check separators in order of preference
            # Note: ' - ' (with spaces) is preferred over '-' to avoid splitting hyphenated words.
            for separator in [':', '=', ' - ']:
                if separator in line:
                    parts = line.split(separator, 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    # Clean key (remove any trailing punctuation/separators)
                    key = re.sub(r'[:=\-\s]+$', '', key).strip()
                    if key:
                        parsed_data[key] = val
                    matched = True
                    break
            
            if not matched and '-' in line:
                # Fallback to single hyphen if no other separator was found
                parts = line.split('-', 1)
                key = parts[0].strip()
                val = parts[1].strip()
                key = re.sub(r'[:=\-\s]+$', '', key).strip()
                if key:
                    parsed_data[key] = val
        
        # Apply global aliases to normalize keys
        normalized_data = {}
        for key, val in parsed_data.items():
            norm_key = key.lower().strip()
            resolved_key = self.global_aliases.get(norm_key, key)
            normalized_data[resolved_key] = val

        return normalized_data
