#!/bin/bash

# Check install has not already run
if [ ! -d lnbits/data ]; then

  # Update package list and install prerequisites
  sudo apt update
  sudo apt install -y software-properties-common curl git
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt install -y python3.9 python3.9-distutils

  # Install Poetry
  curl -sSL https://install.python-poetry.org | python3 -

  # Add Poetry to PATH for the current session
  export PATH="$HOME/.local/bin:$PATH"

  if [ -d lnbits ]; then # Someone didnt follow the install guide
    # Check out the main branch
    git checkout main
  else
    # Clone the LNbits repository
    git clone https://github.com/lnbits/lnbits.git
    cd lnbits

    # Check out the main branch
    git checkout main
  fi
  # Set up the Poetry environment to use Python 3.9
  poetry env use python3.9

  # Make data folder
  mkdir data
  
  # Copy the .env.example to .env
  cp .env.example .env
elif [ ! -d lnbits/wallets ]; then # Another check its not being run from the wrong directory
  # cd into lnbits
  cd lnbits
fi

# Install the dependencies
poetry install --only main

# Set environment variables for LNbits
export LNBITS_ADMIN_UI=true

# Run LNbits
poetry run lnbits