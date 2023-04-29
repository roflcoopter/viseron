#!/usr/bin/env bash

set -e

# Install python deps
pip3 install -r requirements.txt

# Install frontend dependencies
cd /workspaces/viseron/frontend
npm install

# Install pre-commit hooks
cd /workspaces/viseron
pre-commit install

# Set environment variables
cd /var/run/environment
for FILE in *; do echo "export $FILE=$(cat $FILE)" >> $HOME/.bashrc; done

# Symlink config
cd /workspaces/viseron
mkdir -p /workspaces/viseron/config
FILE=/workspaces/viseron/config/config.yaml
if test -f "$FILE"; then
    echo "Config file already exists"
else
    echo "Creating default config"
    python3 -c "import viseron.config; viseron.config.create_default_config('$FILE')"
fi
ln -s /workspaces/viseron/config/config.yaml /config/config.yaml