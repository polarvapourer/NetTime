"""Driver protocol tests use a synthetic child process, never a real router."""
import json
import os
import tempfile
import unittest
from unittest import mock

from nettime.adapters import CommandRouter, from_config
from nettime.router import RouterError, apply_target

DRIVER = '''import json, sys
r = json.load(sys.stdin)
if r['config'].get('fail'):
    print('private-password-must-not-be-repeated', file=sys.stderr)
    sys.exit(1)
if r['config'].get('malformed'):
    print('not json'); sys.exit(0)
state = r['config']['state']
try:
    with open(state) as f: macs = json.load(f)
except FileNotFoundError:
    macs = ['02:00:00:00:00:12']
action = r['action']
if action == 'get_filter': out = {'mode': 'Deny', 'macs': macs, 'max': 64}
elif action == 'get_local_device_id': out = 'controller'
elif action == 'get_devices': out = [{'id':'client','name':'Demo','macs':['02:00:00:00:00:10'],'connectedMacs':['02:00:00:00:00:10'],'isAuthority':False,'nodeType':None}]
elif action == 'set_filter':
    with open(state,'w') as f: json.dump(r['arguments']['macs'], f)
    out = {}
else: sys.exit(1)
print(json.dumps({'ok':True, 'output':out}))
'''


class Adapters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.driver = os.path.join(self.tmp.name, 'router driver.py')
        with open(self.driver, 'w') as f:
            f.write(DRIVER)
        self.config = {'state': os.path.join(self.tmp.name, 'synthetic-state.json')}
        self.router = CommandRouter(self.driver, self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_filter_transaction_preserves_unrelated_and_restores(self):
        self.assertEqual(apply_target(self.router, '02:00:00:00:00:10', True)['status'], 'confirmed')
        self.assertEqual(self.router.get_filter()['macs'], ['02:00:00:00:00:12', '02:00:00:00:00:10'])
        self.assertEqual(apply_target(self.router, '02:00:00:00:00:10', False)['status'], 'confirmed')
        self.assertEqual(self.router.get_filter()['macs'], ['02:00:00:00:00:12'])

    def test_normalises_devices_and_identity(self):
        self.assertEqual(self.router.get_local_device_id(), 'controller')
        device = self.router.get_devices()[0]
        self.assertTrue(device['online'])
        self.assertEqual(device['connectedMacs'], device['macs'])

    def test_errors_never_echo_driver_output(self):
        for key in ('fail', 'malformed'):
            router = CommandRouter(self.driver, dict(self.config, **{key: True}))
            with self.assertRaises(RouterError) as exc:
                router.get_filter()
            self.assertNotIn('private-password', str(exc.exception))

    def test_refuses_invalid_schema(self):
        for data in ({'mode':'Deny','macs':['bad'],'max':10}, {'mode':'Deny','macs':[],'max':True}):
            with mock.patch.object(self.router, 'call', return_value=data):
                with self.assertRaises(RouterError): self.router.get_filter()
        with mock.patch.object(self.router, 'call', return_value=[{'id':'x','name':'x','macs':[],'connectedMacs':[]} ]):
            with self.assertRaises(RouterError): self.router.get_devices()

    def test_old_configuration_defaults_to_linksys(self):
        self.assertEqual(from_config({'host':'192.168.1.1','pin':'test','auth':'synthetic'}).__class__.__name__, 'Router')
        self.assertIsNone(from_config(None))
        with self.assertRaises(ValueError): from_config({'adapter':'unknown'})


if __name__ == '__main__':
    unittest.main()
