"""Explicit router integrations. Command drivers use a small JSON protocol."""
import json
import os
import subprocess
import sys

from .macs import canonical_mac, is_unicast
from .router import HttpsTransport, Router, RouterError, MAX_RESPONSE


class CommandRouter(object):
    def __init__(self, driver, config):
        self.driver = os.path.abspath(driver)
        if not os.path.isfile(self.driver):
            raise ValueError("Router driver file does not exist")
        self.config = config

    def call(self, action, **args):
        command = [sys.executable, self.driver] if self.driver.endswith('.py') else [self.driver]
        request = {'protocol': 1, 'action': action, 'config': self.config, 'arguments': args}
        try:
            result = subprocess.run(command, input=json.dumps(request).encode('utf-8'),
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            raise RouterError('network', 'Router driver could not complete the request')
        if result.returncode or len(result.stdout) > MAX_RESPONSE:
            raise RouterError('router-result', 'Router driver failed; check its private diagnostics')
        try:
            data = json.loads(result.stdout.decode('utf-8'))
        except (ValueError, UnicodeError):
            raise RouterError('schema', 'Router driver returned invalid JSON')
        if not isinstance(data, dict) or data.get('ok') is not True or 'output' not in data:
            raise RouterError('router-result', 'Router driver did not confirm success')
        return data['output']

    def get_filter(self):
        data = self.call('get_filter')
        if not isinstance(data, dict):
            raise RouterError('schema', 'Driver filter response is not an object')
        raw, cap = data.get('macs'), data.get('max')
        if not isinstance(data.get('mode'), str) or not isinstance(raw, list) or not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
            raise RouterError('schema', 'Driver filter response has invalid fields')
        macs = [canonical_mac(m) for m in raw]
        if any(m is None for m in macs):
            raise RouterError('schema', 'Driver returned an invalid MAC filter entry')
        return {'mode': data['mode'], 'raw': list(raw), 'macs': macs, 'max': cap}

    def set_filter(self, mac_list):
        # apply_target always reads before and after this operation, preserving other entries.
        if any(not is_unicast(canonical_mac(m)) for m in mac_list):
            raise RouterError('schema', 'Invalid requested filter list')
        self.call('set_filter', mode='Deny', macs=mac_list)

    def get_devices(self):
        data = self.call('get_devices')
        if not isinstance(data, list):
            raise RouterError('schema', 'Driver device response is not a list')
        out = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('name'), str):
                raise RouterError('schema', 'Invalid driver device identity')
            macs, connected = item.get('macs'), item.get('connectedMacs')
            if not isinstance(macs, list) or not isinstance(connected, list):
                raise RouterError('schema', 'Invalid driver device addresses')
            ms, cs = [canonical_mac(m) for m in macs], [canonical_mac(m) for m in connected]
            if any(m is None for m in ms + cs) or not set(cs).issubset(ms):
                raise RouterError('schema', 'Invalid driver connection addresses')
            if not isinstance(item.get('isAuthority'), bool) or item.get('nodeType') not in (None, 'Master', 'Slave'):
                raise RouterError('schema', 'Driver must identify infrastructure devices explicitly')
            out.append({'id': item['id'][:80], 'name': item['name'][:60], 'macs': ms,
                        'connectedMacs': cs, 'online': bool(cs), 'isAuthority': item['isAuthority'],
                        'nodeType': item['nodeType'], 'interfaces': []})
        return out

    def get_local_device_id(self):
        data = self.call('get_local_device_id')
        if data is not None and not isinstance(data, str):
            raise RouterError('schema', 'Invalid driver controller identity')
        return data


def from_config(cfg):
    if not cfg:
        return None
    adapter = cfg.get('adapter', 'linksys-jnap')  # old saved configurations keep working
    if adapter == 'linksys-jnap':
        return Router(HttpsTransport(cfg['host'], cfg['pin'], cfg['auth']))
    if adapter == 'command':
        return CommandRouter(cfg['driver'], cfg['driverConfig'])
    raise ValueError('Unknown router adapter: %s' % adapter)
