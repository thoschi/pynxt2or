from __future__ import annotations
import os, platform, shutil, sys

def report():
    rows=[]
    rows.append(("Python",sys.version.split()[0],sys.version_info >= (3,10)))
    try:
        import usb, usb.backend.libusb1
        backend=usb.backend.libusb1.get_backend(); rows.append(("PyUSB",getattr(usb,"__version__","?"),backend is not None))
        rows.append(("libusb-1.0","gefunden" if backend else "nicht gefunden",backend is not None))
    except Exception as exc: rows.append(("PyUSB/libusb",str(exc),False))
    try:
        import requests; rows.append(("requests",requests.__version__,True))
    except Exception as exc: rows.append(("requests",str(exc),False))
    try:
        import PySide6; rows.append(("PySide6",PySide6.__version__,True))
    except Exception as exc: rows.append(("PySide6",str(exc),False))
    rows.append(("System",f"{platform.system()} {platform.machine()}",True))
    if platform.system()=="Linux": rows.append(("udev rule","vorhanden" if os.path.exists('/etc/udev/rules.d/70-lego.rules') else "nicht gefunden",os.path.exists('/etc/udev/rules.d/70-lego.rules')))
    return rows
