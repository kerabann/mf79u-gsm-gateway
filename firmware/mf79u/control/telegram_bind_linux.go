//go:build linux

package main

import "syscall"

func bindTelegramInterface(c syscall.RawConn, iface string) error {
	var bindError error
	e := c.Control(func(fd uintptr) {
		bindError = syscall.SetsockoptString(int(fd), syscall.SOL_SOCKET, syscall.SO_BINDTODEVICE, iface)
	})
	if e != nil {
		return e
	}
	return bindError
}
