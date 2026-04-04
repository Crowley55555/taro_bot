#!/bin/sh
set -e
# Том Docker для /data часто монтируется с uid root — даём appuser (10001) запись в SQLite.
if [ -d /data ]; then
    chown -R appuser:appuser /data 2>/dev/null || true
fi
exec gosu appuser "$@"
