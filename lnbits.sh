#!/bin/bash

# Check install has not already run
if [ ! -d lnbits/data ]; then

  # Check Python version
  if python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" ; then
    echo "Python version is 3.9 or higher ... OK"
  else
    echo "Python version is lower than 3.9 ... FAIL"
    exit 1
  fi

  # Update package list and install prerequisites
  sudo apt update
  sudo apt install -y curl git

  # Install Poetry
  curl -sSL https://install.python-poetry.org | python3 -

  # Add Poetry to PATH for the current session
  export PATH="$HOME/.local/bin:$PATH"

  if [ ! -d "lnbits/extensions" ]; then # Followed the install guide
    # Clone the LNbits repository
    git clone https://github.com/lnbits/lnbits.git
    cd lnbits
  fi

  git checkout main
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
export HOST=0.0.0.0

# Run LNbits
poetry run lnbits
