#!/bin/sh
# This script is sourced by conda during deactivation.
# It is best practice to undo the changes made in the activation script.
export PATH=$(echo "$PATH" | sed -e "s|$CONDA_PREFIX/../../scripts:||g" -e "s|:$CONDA_PREFIX/../../scripts||g")
