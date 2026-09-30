# Legacy OpenRobertaUSBNXT analysis

The supplied legacy source has a small application-level surface despite its Java/leJOS/JNI dependency tree.

## State machine

`DISCOVER -> WAIT_FOR_CONNECT_BUTTON_PRESS -> CONNECT_BUTTON_IS_PRESSED -> WAIT_FOR_SERVER -> WAIT_FOR_CMD -> WAIT_EXECUTION -> WAIT_FOR_CMD`.

Registration sends device data + `token` + `cmd=register`; `repeat` means registration succeeded, `abort` means token timeout. Normal polling sends the same device data + `cmd=push`; `repeat` polls again and `download` triggers `/rest/download`. The response `Filename` header determines the NXT filename, shortened exactly like the legacy client and converted to `.rxe`.

## Device operations actually used

The application only needs: discovery, `GET_DEVICE_INFO`, `GET_FIRMWARE_VERSION`, `GET_BATTERY_LEVEL`, `GET_CURRENT_PROGRAM_NAME`, delete, open-write, write, close, start-program and play-tone. File chunks are 58 bytes. This finite LCP subset is implemented directly in `pynxt2or/lcp.py`.

## Server operations actually used

NXT uses `/rest/pushcmd` and `/rest/download`. Although the generic Java classes define update/configuration commands and `/rest/update`, `NXTUSBBTConnector.update()` is empty. No NXT update implementation is therefore missing.

## Legacy-only infrastructure removed

Java 8 i386, `pccomm.jar`, BlueCove, JNI loader, `libjlibnxt.x86.so`, libusb-0.1 and i386 X11 runtime libraries are transport/GUI implementation details, not Open-Roberta semantics.

## Remaining parity gap

Bluetooth discovery/transport is deliberately absent. USB is the target deployment.
