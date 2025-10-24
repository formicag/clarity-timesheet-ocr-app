#!/bin/bash
#
# ROLLBACK TO SAFE VERSION
#
# This script will revert to the last known working version (commit 384e1dd)
# before the performance optimization changes.
#
# Usage:
#   ./ROLLBACK_TO_SAFE_VERSION.sh
#

echo "================================================================================"
echo "⚠️  ROLLBACK TO SAFE VERSION"
echo "================================================================================"
echo ""
echo "This will revert ALL changes and return to commit 384e1dd"
echo "(Checkpoint before performance optimization)"
echo ""
read -p "Are you sure you want to rollback? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

echo ""
echo "Step 1: Checking current status..."
git status

echo ""
echo "Step 2: Discarding all uncommitted changes..."
git reset --hard HEAD

echo ""
echo "Step 3: Rolling back to commit 384e1dd..."
git reset --hard 384e1dd

echo ""
echo "Step 4: Verifying rollback..."
git log --oneline -5

echo ""
echo "================================================================================"
echo "✅ ROLLBACK COMPLETE"
echo "================================================================================"
echo ""
echo "You are now on the safe version with:"
echo "  - Throttling fixes"
echo "  - Name normalization"
echo "  - Project code quality"
echo "  - All working features"
echo ""
echo "WITHOUT the performance optimization changes."
echo ""
echo "To push this rollback to GitHub:"
echo "  git push origin main --force"
echo ""
echo "⚠️  WARNING: Use --force carefully, it will overwrite remote history!"
echo ""
