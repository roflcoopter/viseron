#!/bin/bash

# Loop over files in /var/run/environment and export them
for file in /var/run/environment/*; do
  export $(basename $file)=$(cat $file)
done