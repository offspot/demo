#!/bin/sh

echo "Running web-generator"
gen-server

echo "Running main command"
exec "$@"
