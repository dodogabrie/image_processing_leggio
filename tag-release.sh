#!/bin/bash

# Simple script to create a new tag and keep only the 3 most recent tags

# Check if tag name was provided
if [ -z "$1" ]; then
    echo "Usage: ./tag-release.sh <tag-name> [message]"
    echo "Example: ./tag-release.sh v1.5.5"
    echo "Example: ./tag-release.sh v1.5.5 'Release with bug fixes'"
    exit 1
fi

TAG_NAME=$1
TAG_MESSAGE=$2

if [ -z "$TAG_MESSAGE" ]; then
    echo "Creating tag: $TAG_NAME"
    git tag "$TAG_NAME"
else
    echo "Creating annotated tag: $TAG_NAME"
    echo "Message: $TAG_MESSAGE"
    git tag -a "$TAG_NAME" -m "$TAG_MESSAGE"
fi

echo "Pushing tag to remote..."
git push origin "$TAG_NAME"

echo ""
echo "Current tags:"
git tag --list | sort -V

echo ""
echo "Keeping only the 3 most recent tags..."

# Get all tags sorted by version, skip the last 3 (most recent)
TAGS_TO_DELETE=$(git tag --list | sort -V | head -n -3)

if [ -z "$TAGS_TO_DELETE" ]; then
    echo "No old tags to delete. Done!"
    exit 0
fi

echo "Tags to delete:"
echo "$TAGS_TO_DELETE"
echo ""

# Delete tags locally
echo "Deleting local tags..."
echo "$TAGS_TO_DELETE" | xargs git tag -d

# Delete tags from remote
echo "Deleting remote tags..."
echo "$TAGS_TO_DELETE" | xargs -I {} git push origin --delete {}

echo ""
echo "Done! Remaining tags:"
git tag --list | sort -V
