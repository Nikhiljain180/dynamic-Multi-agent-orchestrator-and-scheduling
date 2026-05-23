#!/bin/sh
set -e
cd /app
npm install
exec "$@"
