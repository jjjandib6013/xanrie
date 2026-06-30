from difflib import SequenceMatcher

class FormMapper:
    def __init__(self, fuzzy_threshold=0.75, global_aliases=None):
        self.fuzzy_threshold = fuzzy_threshold
        # Normalize global aliases to lowercase
        self.global_aliases = {}
        if global_aliases:
            for alias, standard in global_aliases.items():
                self.global_aliases[alias.lower().strip()] = standard.lower().strip()

    def map_fields(self, parsed_record, form_questions, template=None):
        """Maps parsed record keys to form questions.
        
        parsed_record: dict of {key: value}
        form_questions: list of dicts, each representing a question:
                        {
                            "title": str,
                            "type": str,
                            "required": bool,
                            "options": list of str (optional)
                        }
        template: dict (optional) containing mapping configurations.
                  
        Returns:
            mapped_fields: dict of {question_title: value_to_fill}
            unmapped_keys: list of parsed keys that were not mapped
            missing_required: list of required question titles that were not mapped
        """
        mapped_fields = {}
        used_keys = set()
        
        def get_similarity(s1, s2):
            # Strip common characters like colons, question marks, asterisks
            clean_s1 = s1.lower().strip().rstrip('?:* ')
            clean_s2 = s2.lower().strip().rstrip('?:* ')
            return SequenceMatcher(None, clean_s1, clean_s2).ratio()

        template_mappings = template.get("mappings", {}) if template else {}

        # Pass 1: Map using Template (highest priority)
        for question in form_questions:
            q_title = question.get("title", question.get("label"))
            q_title_clean = q_title.strip()
            
            temp_mapping = None
            # Check if this question is in the template
            if q_title_clean in template_mappings:
                temp_mapping = template_mappings[q_title_clean]
            else:
                # Try case-insensitive lookup in template
                for t_key, t_val in template_mappings.items():
                    if t_key.lower().strip() == q_title_clean.lower():
                        temp_mapping = t_val
                        break
            
            if temp_mapping:
                input_key = temp_mapping.get("input_key")
                aliases = temp_mapping.get("aliases", [])
                
                matched_key = None
                
                # 1. Try template input_key
                if input_key and input_key in parsed_record:
                    matched_key = input_key
                # 2. Try template input_key case-insensitive/stripped
                elif input_key:
                    for k in parsed_record:
                        if k.lower().strip() == input_key.lower().strip():
                            matched_key = k
                            break
                            
                # 3. Try template aliases
                if not matched_key:
                    for alias in aliases:
                        for k in parsed_record:
                            if k.lower().strip() == alias.lower().strip():
                                matched_key = k
                                break
                        if matched_key:
                            break
                            
                if matched_key:
                    mapped_fields[q_title] = parsed_record[matched_key]
                    used_keys.add(matched_key)
                    continue

        # Pass 2: Automatic matching for remaining questions (Exact -> Alias -> Fuzzy)
        for question in form_questions:
            q_title = question.get("title", question.get("label"))
            if q_title in mapped_fields:
                continue
                
            q_title_lower = q_title.lower().strip()
            clean_q_title = q_title_lower.rstrip('?:* ')
            matched_key = None
            
            # 1. Exact Match (case-insensitive, ignoring trailing punctuation)
            for k in parsed_record:
                if k in used_keys:
                    continue
                clean_k = k.lower().strip().rstrip('?:* ')
                if clean_k == clean_q_title:
                    matched_key = k
                    break
            
            # 2. Alias Match (using global aliases)
            if not matched_key:
                for k in parsed_record:
                    if k in used_keys:
                        continue
                    k_lower = k.lower().strip()
                    resolved_k = self.global_aliases.get(k_lower, k_lower)
                    if resolved_k == clean_q_title:
                        matched_key = k
                        break
                        
            # 3. Fuzzy Match
            if not matched_key:
                best_score = 0
                best_key = None
                for k in parsed_record:
                    if k in used_keys:
                        continue
                    score = get_similarity(k, q_title)
                    if score >= self.fuzzy_threshold and score > best_score:
                        best_score = score
                        best_key = k
                if best_key:
                    matched_key = best_key
                    
            if matched_key:
                mapped_fields[q_title] = parsed_record[matched_key]
                used_keys.add(matched_key)

        # Identify unmapped keys
        unmapped_keys = [k for k in parsed_record if k not in used_keys]
        
        # Identify missing required fields
        missing_required = []
        for question in form_questions:
            q_title = question.get("title", question.get("label"))
            if question.get("required", False):
                if q_title not in mapped_fields or not str(mapped_fields[q_title]).strip():
                    missing_required.append(q_title)

        return mapped_fields, unmapped_keys, missing_required
