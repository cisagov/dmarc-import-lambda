#!/usr/bin/env bash

###
# Define the name of the Lambda zip file being produced
###
ZIP_FILE=dmarc-import.zip

###
# Set up the Python virtual environment
###
VENV_DIR=/venv
python -m venv $VENV_DIR
source $VENV_DIR/bin/activate

###
# Update pip and setuptools
###
pip install --upgrade pip setuptools

###
# Install dmarc-import
###
pip install https://api.github.com/repos/dhs-ncats/dmarc-import/tarball/develop

###
# Leave the Python virtual environment
###
deactivate

###
# Set up the build directory
###
BUILD_DIR=/build
mkdir -p $BUILD_DIR/bin

###
# Copy all packages, including any hidden dotfiles.  Also copy the
# Lambda handler.
###
cp -rT $VENV_DIR/lib/python3.6/site-packages/ $BUILD_DIR
cp -rT $VENV_DIR/lib64/python3.6/site-packages/ $BUILD_DIR
cp lambda_handler.py $BUILD_DIR

###
# Zip it all up
###
OUTPUT_DIR=/output
if [ ! -d $OUTPUT_DIR ]
then
    mkdir $OUTPUT_DIR
fi

if [ -e $OUTPUT_DIR/$ZIP_FILE ]
then
    rm $OUTPUT_DIR/$ZIP_FILE
fi
cd $BUILD_DIR
zip -rq9 $OUTPUT_DIR/$ZIP_FILE .
