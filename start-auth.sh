#!/bin/sh
echo "[auth] node $(node --version)"
echo "[auth] starting auth-server.js"
exec node auth-server.js
