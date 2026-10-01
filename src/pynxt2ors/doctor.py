from __future__ import annotations
import os, platform, sys

def report():
    rows=[("Python",sys.version.split()[0],sys.version_info >= (3,10))]
    try:
        import usb, usb.backend.libusb1
        backend=usb.backend.libusb1.get_backend(); rows += [("PyUSB",getattr(usb,"__version__","?"),backend is not None),("libusb-1.0","gefunden" if backend else "nicht gefunden",backend is not None)]
    except Exception as exc: rows.append(("PyUSB/libusb",str(exc),False))
    for mod in ("requests","PySide6","serial"):
        try:
            m=__import__(mod); rows.append((mod,getattr(m,"__version__","installiert"),True))
        except Exception as exc: rows.append((mod,str(exc),False))
    rows.append(("System",f"{platform.system()} {platform.machine()}",True))
    if platform.system()=="Linux":
        rule='/etc/udev/rules.d/70-pynxt2ors.rules'; rows.append(("udev rule","vorhanden" if os.path.exists(rule) else "nicht gefunden",os.path.exists(rule)))
    return rows
