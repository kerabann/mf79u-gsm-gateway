//go:build !linux

package main

import (
	"errors"
	"syscall"
)

func bindTelegramInterface(c syscall.RawConn, iface string) error {
	return errors.New("Telegram interface binding requires Linux")
}
