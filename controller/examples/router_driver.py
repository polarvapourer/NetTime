"""STARTER ONLY: implement the router's documented API here before using it.

Read ROUTERS.md. This file does not control any router and always reports failure.
Never replace these stubs with fake successful responses on a real installation.
"""
import json
import sys


def handle(request):
    if request.get('protocol') != 1:
        raise ValueError('Unsupported protocol')
    # request['config']: private values supplied via stdin, not command-line arguments.
    # request['action']: get_filter, get_devices, get_local_device_id or set_filter.
    # request['arguments']: empty for reads; {mode: 'Deny', macs: [...]} for set_filter.
    # Authenticate using the router vendor's documented API or SSH, with TLS/host-key
    # verification. Preserve unrelated configuration; read actual state from the router.
    raise NotImplementedError('Implement a real, validated router integration first')


if __name__ == '__main__':
    try:
        output = handle(json.load(sys.stdin))
        print(json.dumps({'ok': True, 'output': output}))
    except Exception:
        print(json.dumps({'ok': False}))  # no credentials or raw router errors in stdout
        sys.exit(1)
