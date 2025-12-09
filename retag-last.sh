#!/bin/bash

# Repoint the most recent tag (by version order) to the current commit.

# Ensure we're inside a git repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not inside a git repository."
    exit 1
fi

# Pull latest tags to make sure we are using the current view
git fetch --tags >/dev/null 2>&1 || true

LATEST_TAG=$(git tag --list | sort -V | tail -n 1)

if [ -z "$LATEST_TAG" ]; then
    echo "No tags found to retag."
    exit 1
fi

TAG_MESSAGE="$*"

echo "Retagging most recent tag: $LATEST_TAG"

echo "Deleting local tag..."
git tag -d "$LATEST_TAG"

echo "Deleting remote tag..."
git push origin --delete "$LATEST_TAG"

if [ -z "$TAG_MESSAGE" ]; then
    echo "Recreating lightweight tag on current commit..."
    git tag "$LATEST_TAG"
else
    echo "Recreating annotated tag with message: $TAG_MESSAGE"
    git tag -a "$LATEST_TAG" -m "$TAG_MESSAGE"
fi

echo "Pushing updated tag to remote..."
git push origin "$LATEST_TAG"

echo "Done. $LATEST_TAG now points to $(git rev-parse --short HEAD)"
