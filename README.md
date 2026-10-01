# pynxt2ors 0.7.1

64-bit Open-Roberta connector for LEGO NXT, EV3 and SPIKE.

## GUI

The normal GUI deliberately has no robot selector and no Connect button.
Supported connector hardware is detected automatically. Exactly one connector-driven
robot may be attached at a time. **Open Roberta Lab öffnen** stays disabled until exactly one supported robot has been detected and its Open-Roberta `loadSystem` is known.

Server choices:

- private/patched Lab: `https://cora.corvi.schule` (default)
- official Lab: `https://lab.open-roberta.org`

For the private Lab the connector token is added automatically to the deep link.
For the official Lab only `loadSystem=...` is used; pairing remains the official
Open-Roberta workflow.

Automatic local connector detection currently covers NXT, EV3/leJOS and SPIKE
with LEGO firmware. EV3dev and SPIKE/Pybricks use Open-Roberta-side transports
and can be selected as advanced CLI modes.

## Install

```bash
sudo ./install.sh user
# or
sudo ./install.sh linuxmuster
```

## CLI / simulations

```bash
pynxt2ors --debug
pynxt2ors --doctor
pynxt2ors --fake-nxt
pynxt2ors --fake-ev3 --firmware lejos
pynxt2ors --fake-ev3 --firmware ev3dev
pynxt2ors --fake-spike --firmware lego
pynxt2ors --fake-spike --firmware pybricks
pynxt2ors --system ev3dev
pynxt2ors --system spikePybricks
```
