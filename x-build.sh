#!/bin/bash
#===============================================================================
# SCRIPT:       x-build.sh
# DESCRIPTION:  Builds Docker images for the current project
#               Supports both multi-platform and single platform builds
#
# USAGE:        ./x-build.sh
#
# DEPENDENCIES:
#   - docker
#   - docker buildx (for multi-platform builds)
#   - docker-build-manifest.env file with required variables
#
# ENVIRONMENT VARIABLES (from docker-build-manifest.env):
#   - BUILDER_NAME: Name of the Docker buildx builder
#   - NAME: Name of the Docker image
#   - CURR_TAG: Current tag for the Docker image
#
# NOTES:
#   - For multi-platform builds, Docker buildx with QEMU support is required
#   - Multi-platform builds support linux/amd64 and linux/arm64
#===============================================================================

# Load environment variables from build-manifest.env
source docker-build-manifest.env

# verify that we have the necessary environment variables
if [ -z "$BUILDER_NAME" ] || [ -z "$NAME" ] || [ -z "$CURR_TAG" ]; then
  echo "BUILDER_NAME, NAME and CURR_TAG must be set in build-manifest.env"
  exit 1
fi

# ask if we want to build the image for multi platform or current platform only
echo "Do you want to build the image for multi platform or current platform only?"
echo "1. Multi platform (Requires docker buildx support qith qemu - built into macOS Docker Desktop)"
echo "2. Current platform only"
read -p "Enter your choice: " choice
case $choice in
  1)
    echo "Building the image for multi platform"
    # Check if the builder exists
    if docker buildx inspect "$BUILDER_NAME" > /dev/null 2>&1; then
      echo "Builder $BUILDER_NAME already exists. Reusing it."
      docker buildx use "$BUILDER_NAME"
      docker buildx inspect --bootstrap
    else
      # Create a new builder instance
      echo "Builder $BUILDER_NAME does not exist. Creating a new one."
      docker buildx create --name "$BUILDER_NAME" --use
      docker buildx inspect --bootstrap
    fi
    docker buildx build --platform linux/amd64,linux/arm64  -t $NAME:$CURR_TAG .
    ;;
  2)
    echo "Building the image for current platform only"
    docker build -t $NAME:$CURR_TAG .
    ;;
  *)
    echo "Invalid choice!"
    exit 1
    ;;
esac