#!/usr/bin/env bash

#
# This script triggers all test entrypoints located in test/.
# Using this, tests are called in the same way like done by Jenkins.
# You should always execute this before creating a PR.
#
set -x
set -e

for i in `find . -name test_*.sh -type f`; do $i; if [ $? -ne 0 ]; then exit 1; fi; done