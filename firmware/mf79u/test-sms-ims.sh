#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
(cd firmware/mf79u/control; GOTOOLCHAIN=go1.25.12 GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go test -c -o ../build/sms-ims-control-tests .)
docker run --rm -v "$PWD:/work" -w /work mf79u-system-tools:local sh -eu -c '
 cc -O1 -g -fsanitize=address,undefined -Wall -Wextra -Werror firmware/mf79u/src/ims-sms-native-selftest.c -o /tmp/ims-sms-test
 /tmp/ims-sms-test
 firmware/mf79u/build/sms-ims-control-tests -test.run "TestIMS|TestSMSSIP|TestSMS" -test.v
'
