#!/bin/sh

# Rebuild the ZIP files posted for students. Run from any directory.

set -eu

FLIGHTLABFOAM_SETUP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
FLIGHTLABFOAM_DOWNLOAD_DIR="${FLIGHTLABFOAM_SETUP_DIR}/downloads"

mkdir -p "${FLIGHTLABFOAM_DOWNLOAD_DIR}"

cd "${FLIGHTLABFOAM_SETUP_DIR}/macos"
zip -q -r -FS "${FLIGHTLABFOAM_DOWNLOAD_DIR}/FlightLabFoam-macOS.zip" .

cd "${FLIGHTLABFOAM_SETUP_DIR}/windows"
zip -q -r -FS "${FLIGHTLABFOAM_DOWNLOAD_DIR}/FlightLabFoam-Windows.zip" .

cd "${FLIGHTLABFOAM_SETUP_DIR}/linux"
zip -q -r -FS "${FLIGHTLABFOAM_DOWNLOAD_DIR}/FlightLabFoam-Linux.zip" .

echo "Student downloads are ready in:"
echo "${FLIGHTLABFOAM_DOWNLOAD_DIR}"
