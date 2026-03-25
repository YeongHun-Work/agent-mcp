#!/bin/bash
echo "Creating venv and installing packages..."
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Installation complete!"
