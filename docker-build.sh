#!/bin/sh

VERSION=$(cat VERSION)
NAME=ip-cam-recorder

docker build -f Docker/Dockerfile -t tuonglan/${NAME}:${VERSION} .
