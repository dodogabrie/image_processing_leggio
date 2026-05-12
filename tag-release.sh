#!/bin/bash

# Simple script to create a new tag and keep only the 3 most recent tags

# Ensure we're inside a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not inside a git repository."
    exit 1
fi

# Check if tag name was provided
if [ -z "$1" ]; then
    echo "Usage: ./tag-release.sh <tag-name> [message]"
    echo "Example: ./tag-release.sh v1.5.5"
    echo "Example: ./tag-release.sh v1.5.5 'Release with bug fixes'"
    exit 1
fi

TAG_NAME=$1
shift
TAG_MESSAGE="$*"

# Refresh local view of tags
git fetch --tags >/dev/null 2>&1 || true

# If the tag already exists locally or remotely, stop here
if git show-ref --tags --quiet "refs/tags/$TAG_NAME"; then
    echo "Tag already exists locally: $TAG_NAME"
    echo "If you need to move it, use ./retag-last.sh or delete it first."
    exit 1
fi

if git ls-remote --tags origin "refs/tags/$TAG_NAME" >/dev/null 2>&1; then
    if [ -n "$(git ls-remote --tags origin "refs/tags/$TAG_NAME")" ]; then
        echo "Tag already exists on remote: $TAG_NAME"
        echo "If you need to move it, delete it first or use ./retag-last.sh."
        exit 1
    fi
fi

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

# Get all tags sorted by version (ignoring leading v or v.), skip the last 3 (most recent)
TAGS_TO_DELETE=$(
    git tag --list \
    | while read -r tag; do
        norm=$(echo "$tag" | sed 's/^v\\.//; s/^v//')
        printf '%s %s\n' "$norm" "$tag"
      done \
    | sort -V \
    | awk '{print $2}' \
    | head -n -3
)

# Never delete the tag we just created
if [ -n "$TAGS_TO_DELETE" ]; then
    TAGS_TO_DELETE=$(echo "$TAGS_TO_DELETE" | grep -v -x "$TAG_NAME" || true)
fi

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
