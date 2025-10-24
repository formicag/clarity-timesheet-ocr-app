"""
Team roster management and name fuzzy matching
"""
import json
import os
from pathlib import Path
from difflib import SequenceMatcher


class TeamManager:
    """Manages team roster and name matching"""

    def __init__(self, roster_file='team_roster.json'):
        self.roster_file = roster_file
        self.team_members = []
        self.name_aliases = {}
        self.load_roster()

    def load_roster(self):
        """Load team roster from JSON file"""
        roster_path = Path(self.roster_file)

        if roster_path.exists():
            with open(roster_path, 'r') as f:
                data = json.load(f)
                self.team_members = sorted(data.get('team_members', []))
                self.name_aliases = data.get('name_aliases', {})
        else:
            # Create default roster if doesn't exist
            self.team_members = []
            self.name_aliases = {}
            self.save_roster()

    def save_roster(self):
        """Save team roster to JSON file"""
        data = {
            'team_members': sorted(self.team_members),
            'name_aliases': self.name_aliases
        }

        with open(self.roster_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_member(self, name):
        """Add a team member"""
        name = name.strip()
        if name and name not in self.team_members:
            self.team_members.append(name)
            self.team_members.sort()
            self.save_roster()
            return True
        return False

    def remove_member(self, name):
        """Remove a team member"""
        if name in self.team_members:
            self.team_members.remove(name)
            self.save_roster()
            return True
        return False

    def add_alias(self, alias, canonical_name):
        """Add a name alias (maps OCR variations to correct name)"""
        if canonical_name in self.team_members:
            self.name_aliases[alias] = canonical_name
            self.save_roster()
            return True
        return False

    def remove_alias(self, alias):
        """Remove a name alias"""
        if alias in self.name_aliases:
            del self.name_aliases[alias]
            self.save_roster()
            return True
        return False

    def normalize_name(self, ocr_name):
        """
        Normalize an OCR name to the canonical team member name.

        1. Check if exact match in team
        2. Check if it's a known alias
        3. Use fuzzy matching to find best match

        Returns: (normalized_name, confidence, match_type)
        """
        ocr_name = ocr_name.strip()

        # Exact match
        if ocr_name in self.team_members:
            return (ocr_name, 1.0, 'exact')

        # Known alias
        if ocr_name in self.name_aliases:
            canonical = self.name_aliases[ocr_name]
            return (canonical, 1.0, 'alias')

        # Fuzzy match
        best_match = None
        best_ratio = 0.0

        for member in self.team_members:
            ratio = self.similarity_ratio(ocr_name, member)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = member

        # High confidence threshold (0.85 = 85% similar)
        if best_ratio >= 0.85:
            return (best_match, best_ratio, 'fuzzy')

        # Low confidence - return original with warning
        return (ocr_name, best_ratio, 'unknown')

    def similarity_ratio(self, name1, name2):
        """
        Calculate similarity between two names.
        Uses case-insensitive comparison.
        """
        name1_lower = name1.lower().strip()
        name2_lower = name2.lower().strip()

        return SequenceMatcher(None, name1_lower, name2_lower).ratio()

    def find_duplicates_in_database(self, items):
        """
        Find potential duplicate names in database items.

        Args:
            items: List of DynamoDB items

        Returns:
            dict: {canonical_name: [list of variant names found]}
        """
        duplicates = {}
        seen_names = set()

        for item in items:
            resource_name = item.get('ResourceName', '')
            resource_display = item.get('ResourceNameDisplay', resource_name)

            # Normalize the name
            normalized, confidence, match_type = self.normalize_name(resource_display)

            # Track if we found variations
            if normalized not in duplicates:
                duplicates[normalized] = set()

            duplicates[normalized].add(resource_name)
            duplicates[normalized].add(resource_display)

        # Filter to only show actual duplicates (more than one variant)
        result = {}
        for canonical, variants in duplicates.items():
            variants_list = sorted(list(variants))
            if len(variants_list) > 1:
                result[canonical] = variants_list

        return result

    def get_team_members(self):
        """Get list of all team members"""
        return sorted(self.team_members)

    def get_aliases(self):
        """Get dictionary of all aliases"""
        return dict(self.name_aliases)
