#!/bin/bash

apt-get update

# Install IPython
apt-get install -y python-pip python2.7-dev libzmq-dev

pip install boto
pip install "ipython[notebook]"
