#!/bin/bash
WORKDIR="/var/local/aeralogin+imp. backup-07.12.2025/aeralogin+implement/vera-ki-api"
cd "$WORKDIR"
exec "$WORKDIR/venv/bin/python3" server.py
