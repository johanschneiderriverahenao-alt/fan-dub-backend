#!/bin/bash

# Install system dependencies for pydub and ffmpeg
apt-get update
apt-get install -y ffmpeg libsndfile1

# Install Python requirements
pip install -r requirements.txt
