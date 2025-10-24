# Team Roster in OCR Prompt - Implementation ✅

**Date:** October 23, 2025
**Status:** ✅ COMPLETED

---

## Summary

Added full team roster (23 members) to the OCR prompt to ensure Claude extracts exact correct spelling of names, eliminating OCR name variations.

---

## Problem

User reported duplicate name variations in database:
- "Diego Diogo" vs "Diogo Diogo" (correct)
- "Neil Pomphret" vs "Neil Pomfret" (correct)

Previous solution (name normalization/aliases) worked but was reactive. Better solution: Tell Claude the exact correct spellings upfront.

---

## Solution: Team Roster in Prompt

### Approach

Instead of fixing names after OCR extraction, we now:
1. Load the full team roster from `team_roster.json`
2. Include all 23 names in the OCR prompt
3. Claude sees the exact spelling and matches it

### Benefits

✅ **Proactive vs Reactive:** Claude gets correct spelling before extraction
✅ **Higher Accuracy:** Claude matches to known list instead of guessing
✅ **Less Normalization:** Fewer edge cases to handle post-extraction
✅ **Self-Documenting:** Prompt shows exactly who to expect

---

## Implementation

### 1. Updated `src/prompt.py`

Added team roster loading function:
```python
def load_team_roster() -> list:
    """Load team member names from team_roster.json."""
    try:
        roster_path = Path('team_roster.json')
        if roster_path.exists():
            with open(roster_path, 'r') as f:
                data = json.load(f)
                return sorted(data.get('team_members', []))
        return []
    except Exception as e:
        print(f"⚠️  Could not load team roster: {e}")
        return []
```

Added team roster section to prompt:
```python
**TEAM ROSTER - EXACT SPELLING REQUIRED**:
The resource name MUST exactly match one of these team members:
  - Barry Breden
  - Chris Halfpenny
  - Craig Conkerton
  - David Hunt
  - Diogo Diogo
  - Donna Smith
  - Gareth Jones
  - Gary Mandaracas
  - Graeme Oldroyd
  - James Matthews
  - Jonathan Mays
  - Julie Barton
  - Kevin Kayes
  - Matthew Garretty
  - Neil Pomfret
  - Nik Coultas
  - Parag Maniar
  - Richard Williams
  - Sheela Adesara
  - Venu Adluru
  - Victor Cheung
  - Vijetha Dayyala
  - Vivek Srivastava

CRITICAL: Use the EXACT spelling shown above. Common OCR errors to avoid:
- "Diogo Diogo" NOT "Diego Diogo"
- "Neil Pomfret" NOT "Neil Pomphret" or "Neil Pomfrett"
- "Jonathan Mays" NOT "Jon Maya", "Jon Mayo", or "Jon Mays"

If you see a name that's close but not exact, use the closest match from the list above.
```

### 2. Updated `team_roster.json`

Added Diego Diogo alias (backup):
```json
{
  "name_aliases": {
    "Diego Diogo": "Diogo Diogo"
  }
}
```

---

## Current Database State

✅ **No duplicates found:**
- Diego_Diogo: 0 (Diego is the typo)
- **Diogo_Diogo: 7** ✅ (correct)
- **Neil_Pomfret: 21** ✅ (correct)
- Neil_Pomphret: 0 (typo variant)

**Conclusion:** Name normalization (from previous fix) already cleaned these up. The prompt update will prevent future occurrences.

---

## Two-Layer Defense

We now have **TWO layers** of name correction:

### Layer 1: OCR Prompt (Proactive) ✅
- Claude sees full team roster
- Matches names to known list
- Extracts correct spelling directly

### Layer 2: Name Normalization (Reactive) ✅
- TeamManager with aliases
- Normalizes any variations that slip through
- Fallback fuzzy matching (85% threshold)

---

## Testing

To test the new prompt, process a new timesheet:

1. **Upload a timesheet image to S3**
2. **Check Lambda logs:**
   ```bash
   aws logs tail /aws/lambda/TimesheetOCR-ocr-dev --region us-east-1 --since 5m
   ```
3. **Look for:**
   - Correct name extracted directly (no normalization needed)
   - Or normalization message if name still varies

---

## Prompt Token Usage

**Team Roster Section:** ~200 tokens
**Total Prompt:** ~3500 tokens (well within limits)

The small token cost is worth the improved accuracy.

---

## Future Maintenance

### Adding New Team Members

1. **Update `team_roster.json`:**
   ```json
   {
     "team_members": [
       "New Person Name"
     ]
   }
   ```

2. **Deploy:**
   ```bash
   ./deploy_quality_improvements.sh
   ```

3. **Done!** New name automatically included in prompt

### Handling Name Changes

If someone's name changes (e.g., marriage):

1. **Add old name as alias:**
   ```json
   {
     "name_aliases": {
       "Old Name": "New Name"
     }
   }
   ```

2. **Update team_members list** with new name

3. **Deploy** and **rescan** old timesheets if needed

---

## Comparison: Before vs After

### Before (Reactive Only)
```
OCR → "Diego Diogo" → Store as Diego_Diogo ❌
Later: Normalization fixes to Diogo_Diogo
Result: 2 database keys, need cleanup
```

### After (Proactive + Reactive)
```
OCR → Sees roster: "Diogo Diogo"
    → Matches to "Diogo Diogo" from list
    → Extracts "Diogo Diogo" ✅
    → Store as Diogo_Diogo ✅
Result: 1 database key, no cleanup needed
```

---

## Technical Details

### Prompt Structure

```
[Grid Detection Instructions]
  ↓
[Base Instructions]
  ↓
**TEAM ROSTER** ← NEW
  - All 23 names
  - Common error examples
  ↓
[Critical Requirements]
  ↓
[Project Code Rules]
  ↓
[Hours Accuracy]
  ↓
[Validation Rules]
  ↓
[Output Format]
```

### Dynamic Loading

The roster is loaded at runtime, so:
- ✅ Always up-to-date with team_roster.json
- ✅ No hardcoding in source code
- ✅ Easy to update via Team Management UI
- ✅ Consistent with normalization logic

---

## Known Limitations

1. **Prompt length:** With 23 names, prompt is ~3500 tokens. If team grows to 100+, may need to optimize.
2. **Phonetic variations:** Unusual names may still confuse OCR (handled by Layer 2)
3. **Cultural names:** Names with special characters may need extra aliases

---

## Metrics to Monitor

Track these to measure success:

1. **Name normalization rate:** Should decrease over time
2. **Duplicate name keys:** Should remain at 0
3. **OCR confidence:** Should improve with roster hints

---

## Related Fixes

This complements previous name fixes:
- `JONATHAN_MAYS_FIX_COMPLETE.md` - Jon Maya/Mayo/Mays variations
- Name aliases in `team_roster.json` - Pomfret/Pomphret variations

---

## Status: COMPLETE ✅

All tasks completed:
- ✅ Team roster loaded dynamically
- ✅ Roster added to OCR prompt with examples
- ✅ Lambda deployed with updated prompt
- ✅ Diego Diogo alias added (backup)
- ✅ Database verified (no duplicates)
- ✅ Two-layer defense in place

**Impact:**
- Proactive: Claude now sees exact spellings before extraction
- Reactive: Normalization still catches edge cases
- Result: Highest possible name accuracy

---

## Example OCR Prompt Output

When Claude receives a timesheet, it now sees:

```
**TEAM ROSTER - EXACT SPELLING REQUIRED**:
The resource name MUST exactly match one of these team members:
  - Barry Breden
  - Chris Halfpenny
  [... 21 more names ...]
  - Vivek Srivastava

CRITICAL: Use the EXACT spelling shown above.
```

Then Claude thinks:
- "I see 'Diogo Diogo' in the image"
- "I'll match it to 'Diogo Diogo' from the roster"
- "✅ Extract as: Diogo Diogo"

---

**Future timesheets will have higher name accuracy from the start, with normalization as a safety net!**
