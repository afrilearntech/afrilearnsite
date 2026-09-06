#!/usr/bin/env bash
set -Eeuo pipefail

readonly APP_DIR="/srv/afrilearnsite"
readonly BRANCH="main"
readonly LOCK_FILE="/var/lock/afrilearnsite-deploy.lock"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    echo "Another afrilearnsite deployment is already running." >&2
    exit 1
fi

cd "${APP_DIR}"

if [[ ! -d .git || ! -x venv/bin/python ]]; then
    echo "The production checkout or Python environment is missing." >&2
    exit 1
fi

if [[ "$(git branch --show-current)" != "${BRANCH}" ]]; then
    echo "Production must be checked out on ${BRANCH}." >&2
    exit 1
fi

# Uploads, collected static files, and the SQLite database are intentionally
# untracked. Refuse only changes to tracked source files.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Production has modified tracked files; refusing to overwrite them." >&2
    git status --short --untracked-files=no >&2
    exit 1
fi

export GIT_TERMINAL_PROMPT=0
git fetch --prune origin "${BRANCH}"
target_commit="$(git rev-parse FETCH_HEAD)"

if ! git merge-base --is-ancestor HEAD "${target_commit}"; then
    echo "Production history cannot be fast-forwarded to origin/${BRANCH}." >&2
    exit 1
fi

git merge --ff-only "${target_commit}"
venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
venv/bin/python manage.py check --deploy --fail-level WARNING
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput

nginx -t
systemctl restart gunicorn
systemctl is-active --quiet gunicorn
systemctl reload nginx

curl --fail --silent --show-error --location \
    --retry 5 --retry-delay 2 --retry-connrefused \
    --max-time 20 https://afrilearntech.com/ >/dev/null

echo "Deployed $(git rev-parse --short HEAD) to afrilearntech.com"
