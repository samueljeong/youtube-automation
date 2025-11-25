#!/usr/bin/env bash
# Render build script

set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python init_db_postgres.py

echo "Adding YouTube token table..."
python add_youtube_token_table.py

echo "Build complete!"
