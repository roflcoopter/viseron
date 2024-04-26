#!/usr/bin/env bash

set -e

# Set workspace dir
export WORKSPACE_DIR=$PWD
echo "export WORKSPACE_DIR=$PWD" >> $HOME/.bashrc

# Install python deps
python3 -m pip install -r requirements.txt

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

# Enable terminal colors
sed -i 's/#force_color_prompt=yes/force_color_prompt=yes/g' $HOME/.bashrc

# Create default config if it is missing
cd $WORKSPACE_DIR
mkdir -p $WORKSPACE_DIR/config
FILE=$WORKSPACE_DIR/config/config.yaml
if test -f "$FILE"; then
    echo "Config file already exists"
else
    echo "Creating default config"
    python3 -c "import viseron.config; viseron.config.create_default_config('$FILE')"
fi

# Create symlink to config file
FILE=/config/config.yaml
if test -f "$FILE"; then
    echo "Config symlink already exists"
else
    echo "Creating config symlink"
    ln -s $WORKSPACE_DIR/config/config.yaml /config/config.yaml
fi

# Create .env.local
FILE=$WORKSPACE_DIR/frontend/.env.local
if test -f "$FILE"; then
    echo "Frontend .env.local already exists"
else
    echo "Creating frontend .env.local"
    echo "VITE_PROXY_HOST=localhost:8888" > $FILE
fi

# Generate locale
locale-gen
