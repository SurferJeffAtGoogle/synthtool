# build from the root of this repo:
# docker build -t gcr.io/cloud-devrel-kokoro-resources/synthtool -f docker/owlbot/nodejs/Dockerfile .
FROM python:3.6.12-buster

WORKDIR /

######################## Install nodejs.
# Use `nvm` to bootstrap the installation of node.js and npm.
# To learn more: https://github.com/nvm-sh/nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.35.3/install.sh | bash

# Use the latest LTS version of nodejs.  This can change over time, but
# should prevent the need to modify this file every year.
# The "npm config set unsafe-perm true" is necessary because npm will refuse to perform
# some operations if the user is running as root.  The root user of a docker image
# doesn't have root permissions on the machine, so it's safe to execute them.
# I learned this from https://geedew.com/What-does-unsafe-perm-in-npm-actually-do/
RUN /bin/bash -c "source /root/.nvm/nvm.sh && nvm install --lts && npm config set unsafe-perm true"

###################### Install synthtool's requirements.
COPY requirements.txt /synthtool/requirements.txt
RUN pip install -r /synthtool/requirements.txt

# Put synthtool in the PYTHONPATH so we can invoke it with `python -m autosynth`.
ENV PYTHONPATH="/synthtool"

# Copy synthtool.
COPY synthtool /synthtool/synthtool
COPY autosynth /synthtool/autosynth
COPY docker /synthtool/docker

