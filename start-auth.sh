#!/bin/sh
# Wrapper so node errors appear in Railway logs before any crash
echo "[auth] node $(node --version)"
echo "[auth] testing better-sqlite3..."
node -e "const db=require('better-sqlite3')('/tmp/probe.db');db.close();require('fs').unlinkSync('/tmp/probe.db');console.log('[auth] sqlite ok')"
echo "[auth] starting auth-server.js"
exec node auth-server.js
