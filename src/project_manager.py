"""
Project code/name management and normalization
Prevents OCR variations from creating duplicate projects
"""
import json
import re
from pathlib import Path
from difflib import SequenceMatcher


class ProjectManager:
    """Manages project master list and normalizes OCR variations"""

    def __init__(self, master_file='project_master.json'):
        self.master_file = master_file
        self.projects = []
        self.normalization_rules = {}
        self.load_master_list()

    def load_master_list(self):
        """Load project master list from JSON file"""
        master_path = Path(self.master_file)

        if master_path.exists():
            with open(master_path, 'r') as f:
                data = json.load(f)
                self.projects = data.get('projects', [])
                self.normalization_rules = data.get('normalization_rules', {})
        else:
            # Create default structure
            self.projects = []
            self.normalization_rules = {
                'code_patterns': {
                    'remove_spaces': True,
                    'uppercase': True,
                    'zero_vs_o': True
                },
                'name_patterns': {
                    'trim_whitespace': True,
                    'normalize_spaces': True,
                    'title_case': True
                }
            }
            self.save_master_list()

    def save_master_list(self):
        """Save project master list to JSON file"""
        data = {
            'projects': self.projects,
            'normalization_rules': self.normalization_rules
        }

        with open(self.master_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_project(self, code, name):
        """Add a new project to the master list"""
        # Check if already exists
        for project in self.projects:
            if project['code'] == code:
                return False

        self.projects.append({
            'code': code,
            'name': name,
            'aliases': {
                'codes': [],
                'names': []
            }
        })
        self.projects.sort(key=lambda x: x['code'])
        self.save_master_list()
        return True

    def remove_project(self, code):
        """Remove a project from master list"""
        for i, project in enumerate(self.projects):
            if project['code'] == code:
                del self.projects[i]
                self.save_master_list()
                return True
        return False

    def update_project(self, code, new_name):
        """Update project name"""
        for project in self.projects:
            if project['code'] == code:
                project['name'] = new_name
                self.save_master_list()
                return True
        return False

    def add_alias(self, code, alias_type, alias_value):
        """
        Add an alias for a project code or name

        Args:
            code: The canonical project code
            alias_type: 'code' or 'name'
            alias_value: The variant to map to canonical
        """
        for project in self.projects:
            if project['code'] == code:
                key = 'codes' if alias_type == 'code' else 'names'
                if alias_value not in project['aliases'][key]:
                    project['aliases'][key].append(alias_value)
                    self.save_master_list()
                return True
        return False

    def remove_alias(self, code, alias_type, alias_value):
        """Remove an alias"""
        for project in self.projects:
            if project['code'] == code:
                key = 'codes' if alias_type == 'code' else 'names'
                if alias_value in project['aliases'][key]:
                    project['aliases'][key].remove(alias_value)
                    self.save_master_list()
                return True
        return False

    def normalize_code(self, ocr_code):
        """
        Normalize project code using rules

        Handles common OCR errors:
        - Extra spaces
        - O vs 0 (letter O vs zero)
        - Case inconsistency
        """
        if not ocr_code:
            return ocr_code

        normalized = str(ocr_code)

        rules = self.normalization_rules.get('code_patterns', {})

        if rules.get('remove_spaces', True):
            normalized = normalized.replace(' ', '')

        if rules.get('uppercase', True):
            normalized = normalized.upper()

        if rules.get('zero_vs_o', True):
            # This is tricky - we'll handle it in fuzzy matching
            pass

        return normalized.strip()

    def normalize_name(self, ocr_name):
        """
        Normalize project name using rules

        Handles:
        - Extra whitespace
        - Multiple spaces
        - Case inconsistency
        """
        if not ocr_name:
            return ocr_name

        normalized = str(ocr_name)

        rules = self.normalization_rules.get('name_patterns', {})

        if rules.get('trim_whitespace', True):
            normalized = normalized.strip()

        if rules.get('normalize_spaces', True):
            # Replace multiple spaces with single space
            normalized = re.sub(r'\s+', ' ', normalized)

        if rules.get('title_case', True):
            # Title case for consistency
            normalized = normalized.title()

        return normalized

    def match_project(self, ocr_code, ocr_name):
        """
        Match OCR'd project code/name to master list

        Returns: (matched_code, matched_name, confidence, match_type)

        Match types:
        - 'exact': Exact match
        - 'normalized': Match after normalization
        - 'alias': Matched a known alias
        - 'fuzzy': Fuzzy match (high confidence)
        - 'new': No match found (low confidence)
        """
        # Normalize inputs
        norm_code = self.normalize_code(ocr_code)
        norm_name = self.normalize_name(ocr_name)

        # 1. Exact match on code
        for project in self.projects:
            if project['code'] == norm_code:
                return (project['code'], project['name'], 1.0, 'exact')

        # 2. Check code aliases
        for project in self.projects:
            for alias_code in project['aliases']['codes']:
                if self.normalize_code(alias_code) == norm_code:
                    return (project['code'], project['name'], 1.0, 'alias')

        # 3. Fuzzy match on code (handle O vs 0)
        best_code_match = None
        best_code_ratio = 0.0

        for project in self.projects:
            ratio = self.similarity_with_substitutions(norm_code, project['code'])
            if ratio > best_code_ratio:
                best_code_ratio = ratio
                best_code_match = project

        # 4. Fuzzy match on name
        best_name_match = None
        best_name_ratio = 0.0

        for project in self.projects:
            ratio = self.similarity_ratio(norm_name, project['name'])
            if ratio > best_name_ratio:
                best_name_ratio = ratio
                best_name_match = project

        # Decide which match to use
        # High confidence threshold for code (95%)
        if best_code_ratio >= 0.95 and best_code_match:
            return (best_code_match['code'], best_code_match['name'], best_code_ratio, 'fuzzy-code')

        # High confidence threshold for name (90%)
        if best_name_ratio >= 0.90 and best_name_match:
            return (best_name_match['code'], best_name_match['name'], best_name_ratio, 'fuzzy-name')

        # If both are decent, prefer code match
        if best_code_ratio >= 0.85 and best_code_match:
            return (best_code_match['code'], best_code_match['name'], best_code_ratio, 'fuzzy-code')

        # No good match - return normalized version
        return (norm_code, norm_name, 0.0, 'new')

    def similarity_ratio(self, str1, str2):
        """Calculate similarity between two strings"""
        if not str1 or not str2:
            return 0.0

        str1_lower = str1.lower().strip()
        str2_lower = str2.lower().strip()

        return SequenceMatcher(None, str1_lower, str2_lower).ratio()

    def similarity_with_substitutions(self, str1, str2):
        """
        Calculate similarity with common OCR substitutions
        Handles: O vs 0, I vs 1, S vs 5, etc.
        """
        # Create variants with common substitutions
        variants = [str1]

        # O <-> 0
        if 'O' in str1 or '0' in str1:
            variants.append(str1.replace('O', '0'))
            variants.append(str1.replace('0', 'O'))

        # I <-> 1
        if 'I' in str1 or '1' in str1:
            variants.append(str1.replace('I', '1'))
            variants.append(str1.replace('1', 'I'))

        # S <-> 5
        if 'S' in str1 or '5' in str1:
            variants.append(str1.replace('S', '5'))
            variants.append(str1.replace('5', 'S'))

        # Find best match among all variants
        best_ratio = 0.0
        for variant in variants:
            ratio = SequenceMatcher(None, variant, str2).ratio()
            if ratio > best_ratio:
                best_ratio = ratio

        return best_ratio

    def find_duplicates_in_database(self, items):
        """
        Find potential duplicate projects in database items

        Returns: dict of {canonical_project: [list of variants]}
        """
        project_variants = {}

        for item in items:
            code = item.get('ProjectCode', '')
            name = item.get('ProjectName', '')

            if not code or not name:
                continue

            # Match to master list
            matched_code, matched_name, confidence, match_type = self.match_project(code, name)

            # Group by matched project
            key = f"{matched_code}|{matched_name}"
            if key not in project_variants:
                project_variants[key] = {
                    'canonical_code': matched_code,
                    'canonical_name': matched_name,
                    'variants': set()
                }

            project_variants[key]['variants'].add(f"{code}|{name}")

        # Filter to only show actual duplicates
        duplicates = {}
        for key, data in project_variants.items():
            if len(data['variants']) > 1:
                duplicates[key] = {
                    'canonical_code': data['canonical_code'],
                    'canonical_name': data['canonical_name'],
                    'variants': sorted(list(data['variants']))
                }

        return duplicates

    def get_projects(self):
        """Get list of all projects"""
        return sorted(self.projects, key=lambda x: x['code'])

    def get_project_by_code(self, code):
        """Get a project by its code"""
        for project in self.projects:
            if project['code'] == code:
                return project
        return None
