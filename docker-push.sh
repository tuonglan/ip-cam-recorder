#!/bin/sh

VERSION=$(cat VERSION)
NAME=ip-cam-recorder

docker push tuonglan/${NAME}:${VERSION}
