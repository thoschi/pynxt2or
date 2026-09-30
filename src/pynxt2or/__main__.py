from __future__ import annotations

import argparse
import json
import logging
import threading

from .doctor import report
from .lcp import NXTUSB


def main():
    p = argparse.ArgumentParser(prog="pynxt2or")
    p.add_argument("--probe", action="store_true", help="NXT finden und Geräteinformationen per LCP lesen")
    p.add_argument("--doctor", action="store_true", help="Python-, GUI- und USB-Abhängigkeiten prüfen")
    p.add_argument("--simulate", action="store_true", help="Connector ohne NXT/Server einmal vollständig durchlaufen")
    p.add_argument(
        "--fake-nxt",
        action="store_true",
        help="GUI mit simuliertem NXT, aber echtem Open-Roberta-Server starten",
    )
    p.add_argument("--server", default="https://lab.open-roberta.org:443")
    p.add_argument("--debug", action="store_true")
    a = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if a.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if a.doctor:
        ok = True
        for name, value, good in report():
            print(f"{'OK' if good else '!!':2}  {name:14} {value}")
            ok &= good
        return 0 if ok else 1

    if a.probe:
        with NXTUSB() as nxt:
            print(json.dumps(nxt.device_info_for_server(), indent=2, ensure_ascii=False))
        return 0

    if a.simulate:
        from .connector import Connector, State
        from .sim import SimNXT, SimServer

        done = threading.Event()

        def cb(s, m):
            print(f"{s.value:12} {m}")
            if s == State.READY:
                c.request_connect()
            if s == State.CONNECTED and m == "Programm beendet":
                done.set()
                c.stop()

        c = Connector(cb, nxt_factory=SimNXT, server=SimServer())
        t = threading.Thread(target=c.run)
        t.start()
        done.wait(8)
        c.stop()
        t.join(2)
        if not done.is_set():
            raise SystemExit("Simulation nicht vollständig durchlaufen")
        print("Simulation erfolgreich.")
        return 0

    from .gui import main as gui_main
    return gui_main(a.server, fake_nxt=a.fake_nxt)


if __name__ == "__main__":
    raise SystemExit(main())
