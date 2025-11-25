#!/usr/bin/env bash
# Render build script

set -o errexit

echo "Installing Korean fonts..."
apt-get update
apt-get install -y fonts-nanum fonts-nanum-extra

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Initializing database..."
python init_db_postgres.py

echo "Adding YouTube token table..."
python add_youtube_token_table.py

echo "Build complete!"
