#!/bin/sh
# Keep lockfile behavior consistent across distributions with older npm releases.
set -eu
exec npx --yes npm@10.9.9 ci "$@"
