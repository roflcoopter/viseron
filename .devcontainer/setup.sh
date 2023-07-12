#!/usr/bin/env bash

set -e

# Set workspace dir
export WORKSPACE_DIR=$PWD
echo "export WORKSPACE_DIR=$PWD" >> $HOME/.bashrc

# Install python deps
pip3 install -r requirements.txt

# Install frontend dependencies
cd $WORKSPACE_DIR/frontend
npm install

# Install pre-commit hooks
cd $WORKSPACE_DIR
pre-commit install

# Set environment variables
cd /var/run/environment
for FILE in *
do
    echo "export $FILE=$(cat $FILE)" >> $HOME/.bashrc
    sed -i "s/$FILE=true/$FILE=false/g" $HOME/.bashrc
done

# Symlink config
cd $WORKSPACE_DIR
mkdir -p $WORKSPACE_DIR/config
FILE=$WORKSPACE_DIR/config/config.yaml
if test -f "$FILE"; then
    echo "Config file already exists"
else
    echo "Creating default config"
    python3 -c "import viseron.config; viseron.config.create_default_config('$FILE')"
fi
ln -s $WORKSPACE_DIR/config/config.yaml /config/config.yaml
