#!/usr/bin/env bash

# Terminal launcher for FlightLabFoam on Linux.
# FlightLabFoam is pinned so every student uses the same build.
#
# The first launch downloads uv, Python 3.12, and the promoted build into a
# FlightLabFoam-only folder under ~/.local/share/flightlabfoam.  Later launches
# start that installed copy directly, so nothing is downloaded or re-resolved
# again until the instructor promotes a new build.  The machine settings live
# in the same folder, outside the environment, so updates keep them.
#
# Run it with:  bash "Start FlightLabFoam.sh"

set -u
set -o pipefail

FLIGHTLABFOAM_DEFAULT_COMMIT="63839bb765f2f1d9e78cf3d953b3f0b97849850a"
FLIGHTLABFOAM_RELEASE_URL="https://raw.githubusercontent.com/byuflowlab/FlightLabFoam/master/student_setup/release.txt"
FLIGHTLABFOAM_DATA_ROOT="${XDG_DATA_HOME:-${HOME}/.local/share}/flightlabfoam"
FLIGHTLABFOAM_UV_DIR="${FLIGHTLABFOAM_DATA_ROOT}/uv"
FLIGHTLABFOAM_UV="${FLIGHTLABFOAM_UV_DIR}/uv"
FLIGHTLABFOAM_RELEASE_FILE="${FLIGHTLABFOAM_DATA_ROOT}/release.txt"
FLIGHTLABFOAM_RELEASE_TEMP="${FLIGHTLABFOAM_DATA_ROOT}/release-download.txt"
FLIGHTLABFOAM_ENV_DIR="${FLIGHTLABFOAM_DATA_ROOT}/env"
FLIGHTLABFOAM_ENV_TEMP="${FLIGHTLABFOAM_DATA_ROOT}/env-install"
FLIGHTLABFOAM_INSTALLED_FILE="${FLIGHTLABFOAM_DATA_ROOT}/installed.txt"
FLIGHTLABFOAM_SETTINGS_FILE="${FLIGHTLABFOAM_DATA_ROOT}/settings.yaml"
FLIGHTLABFOAM_PYTHON="${FLIGHTLABFOAM_ENV_DIR}/bin/python"
FLIGHTLABFOAM_TEST_ONLY="${FLIGHTLABFOAM_TEST_ONLY:-0}"

wait_for_key() {
    echo "Press any key to close this window."
    if [[ "${FLIGHTLABFOAM_TEST_ONLY}" != "1" ]]; then
        read -r -s -n 1
    fi
}

# Download a URL to a file with whichever of curl or wget the machine has.
fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf --connect-timeout 5 --max-time 15 "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=15 --tries=1 -O "$2" "$1"
    else
        return 1
    fi
}

echo "FlightLabFoam"
echo "=============================================="
echo

mkdir -p "${FLIGHTLABFOAM_DATA_ROOT}"

if [[ ! -x "${FLIGHTLABFOAM_UV}" ]]; then
    echo "First-time setup: downloading the FlightLabFoam launcher..."
    echo "This does not need administrator access."
    echo
    mkdir -p "${FLIGHTLABFOAM_UV_DIR}"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${FLIGHTLABFOAM_UV_DIR}" sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${FLIGHTLABFOAM_UV_DIR}" sh
    else
        echo "This computer has neither curl nor wget. Install one of them (for example"
        echo "'sudo apt install curl' on Ubuntu) and run this launcher again."
        wait_for_key
        exit 1
    fi
    if [[ ! -x "${FLIGHTLABFOAM_UV}" ]]; then
        echo
        echo "Setup could not be downloaded. Check the internet connection and try again."
        echo "If the problem continues, take a screenshot of this window and send it to your TA."
        wait_for_key
        exit 1
    fi
fi

echo "Checking for an update..."
if fetch "${FLIGHTLABFOAM_RELEASE_URL}" "${FLIGHTLABFOAM_RELEASE_TEMP}" \
    && grep -Eq '^[0-9a-f]{40}$' "${FLIGHTLABFOAM_RELEASE_TEMP}"; then
    mv "${FLIGHTLABFOAM_RELEASE_TEMP}" "${FLIGHTLABFOAM_RELEASE_FILE}"
elif [[ -f "${FLIGHTLABFOAM_RELEASE_FILE}" ]] \
    && grep -Eq '^[0-9a-f]{40}$' "${FLIGHTLABFOAM_RELEASE_FILE}"; then
    echo "The update check was unavailable; using the most recent downloaded version."
else
    echo "The update check was unavailable; using the version included with this launcher."
    printf '%s\n' "${FLIGHTLABFOAM_DEFAULT_COMMIT}" > "${FLIGHTLABFOAM_RELEASE_FILE}"
fi

read -r FLIGHTLABFOAM_COMMIT < "${FLIGHTLABFOAM_RELEASE_FILE}"
FLIGHTLABFOAM_INSTALLED=""
if [[ -f "${FLIGHTLABFOAM_INSTALLED_FILE}" ]]; then
    read -r FLIGHTLABFOAM_INSTALLED < "${FLIGHTLABFOAM_INSTALLED_FILE}"
fi

if [[ ! -x "${FLIGHTLABFOAM_PYTHON}" || "${FLIGHTLABFOAM_INSTALLED}" != "${FLIGHTLABFOAM_COMMIT}" ]]; then
    FLIGHTLABFOAM_REQUIREMENT="flightlabfoam[pinned] @ https://github.com/byuflowlab/FlightLabFoam/archive/${FLIGHTLABFOAM_COMMIT}.zip"
    echo "Installing build ${FLIGHTLABFOAM_COMMIT:0:8}..."
    echo "The first install downloads Python and FlightLabFoam's libraries (about 60 MB)"
    echo "and can take a few minutes. Later updates reuse what is already downloaded."
    echo
    rm -rf "${FLIGHTLABFOAM_ENV_TEMP}"
    if "${FLIGHTLABFOAM_UV}" python install 3.12 \
        && "${FLIGHTLABFOAM_UV}" venv --quiet --python 3.12 "${FLIGHTLABFOAM_ENV_TEMP}" \
        && "${FLIGHTLABFOAM_UV}" pip install --python "${FLIGHTLABFOAM_ENV_TEMP}/bin/python" "${FLIGHTLABFOAM_REQUIREMENT}"; then
        rm -rf "${FLIGHTLABFOAM_ENV_DIR}"
        mv "${FLIGHTLABFOAM_ENV_TEMP}" "${FLIGHTLABFOAM_ENV_DIR}"
        printf '%s\n' "${FLIGHTLABFOAM_COMMIT}" > "${FLIGHTLABFOAM_INSTALLED_FILE}"
        echo
    else
        rm -rf "${FLIGHTLABFOAM_ENV_TEMP}"
        echo
        if [[ -x "${FLIGHTLABFOAM_PYTHON}" && -n "${FLIGHTLABFOAM_INSTALLED}" ]]; then
            echo "The update could not be installed; starting the previously installed build instead."
            FLIGHTLABFOAM_COMMIT="${FLIGHTLABFOAM_INSTALLED}"
        else
            echo "FlightLabFoam could not be installed. Check the internet connection and try again."
            echo "If the problem continues, take a screenshot of this window and send it to your TA."
            wait_for_key
            exit 1
        fi
    fi
fi

echo "Build: ${FLIGHTLABFOAM_COMMIT:0:8}"
echo "Starting FlightLabFoam. Your web browser will open when it is ready."
echo "If no browser opens, copy the http://127.0.0.1 address printed below into one."
echo
echo "Keep this window open while using FlightLabFoam."
echo "Click Exit in the app, close this window, or press Control-C when you are finished."
echo

if [[ "${FLIGHTLABFOAM_TEST_ONLY}" == "1" ]]; then
    # The server runs until stopped, so the smoke test only imports the app.
    "${FLIGHTLABFOAM_PYTHON}" -c "import flightlabfoam.app; print('FlightLabFoam imports OK')"
else
    "${FLIGHTLABFOAM_PYTHON}" -m flightlabfoam --settings "${FLIGHTLABFOAM_SETTINGS_FILE}"
fi

FLIGHTLABFOAM_STATUS=$?
if [[ ${FLIGHTLABFOAM_STATUS} -ne 0 && ${FLIGHTLABFOAM_STATUS} -ne 130 ]]; then
    echo
    echo "FlightLabFoam stopped because of an error."
    echo "Take a screenshot of this window and send it to your TA."
    wait_for_key
fi

exit ${FLIGHTLABFOAM_STATUS}
