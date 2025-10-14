#!/usr/bin/env bash
set -e  # exit immediately on error

echo "🚀 Starting Ryu environment setup..."

sudo apt update && sudo apt upgrade -y

if [ ! -f "Miniconda3-latest-Linux-x86_64.sh" ]; then
    echo "Downloading Miniconda..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
fi

echo "Installing Miniconda..."
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3

eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
conda init bash

rm -f Miniconda3-latest-Linux-x86_64.sh

echo "Verifying Conda installation..."
conda --version || { echo "Conda not found! Exiting."; exit 1; }

echo "Creating Conda environment..."
conda env create -f ryuenv_working.yml || {
    echo "⚠️  Environment already exists, skipping create..."
}

conda activate ryuenv

echo "Installing Mininet and Open vSwitch..."
sudo apt install -y mininet openvswitch-switch

echo "✅ Setup complete!"

