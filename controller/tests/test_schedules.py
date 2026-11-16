import copy
import json
import unittest

from nettime.policy import active_away, decide, init_tz, london, split_charge, validate_settings
from test_policy import DASHBOARD_EXPORT, full
from fakes import IPAD, OTHER, utc

init_tz()


def school(s):
    s['schoolHours'] = {'enabled': True, 'start': '09:00', 'end': '15:00'}
    return s


def away(s, start='08:00', end='16:00', days=None):
    s['awayWindows'] = [{'id': 'away-test', 'label': 'Out of home', 'enabled': True,
                         'days': days or ['mon'], 'start': start, 'end': end}]
    return s


class Schedules(unittest.TestCase):
    def test_old_settings_migrate_disabled(self):
        s, errors = validate_settings(json.loads(DASHBOARD_EXPORT))
        self.assertEqual(errors, [])
        self.assertFalse(s['schoolHours']['enabled'])
        self.assertEqual(s['awayWindows'], [])

    def test_school_boundaries_override_exhausted_and_paused(self):
        s = school(full()); s['leisurePaused'] = True
        for hour, minute, kind in [(8, 59, 'block-paused'), (9, 0, 'allow-exception'),
                                    (14, 59, 'allow-exception'), (15, 0, 'block-paused')]:
            self.assertEqual(decide(s, london(utc(2026, 11, 16, hour, minute)), 99999)['kind'], kind)
        self.assertTrue(decide(s, london(utc(2026, 11, 14, 9)), 99999)['block'])
        s['schoolHours']['enabled'] = False
        self.assertTrue(decide(s, london(utc(2026, 11, 16, 10)), 99999)['block'])

    def test_school_charge_edges_bst_and_gmt(self):
        s = school(full())
        for month, day, start_hour, end_hour in [(11, 16, 9, 15), (6, 15, 8, 14)]:
            r = split_charge(s, utc(2026, month, day, start_hour - 1, 59, 50), utc(2026, month, day, start_hour, 0, 10))
            self.assertAlmostEqual(sum(r.values()), 10)
            r = split_charge(s, utc(2026, month, day, end_hour - 1, 59, 50), utc(2026, month, day, end_hour, 0, 10))
            self.assertAlmostEqual(sum(r.values()), 10)

    def test_away_only_pauses_counting(self):
        s = away(full())
        at = london(utc(2026, 11, 16, 10))
        self.assertIsNotNone(active_away(s, at))
        self.assertFalse(decide(s, at, 0)['block'])
        self.assertTrue(decide(s, at, 99999)['block'])
        self.assertEqual(split_charge(s, utc(2026, 11, 16, 8), utc(2026, 11, 16, 16)), {})
        self.assertIsNone(active_away(s, london(utc(2026, 11, 16, 16))))
        self.assertIsNone(active_away(s, london(utc(2026, 11, 17, 10))))
        s['awayWindows'][0]['enabled'] = False
        self.assertIsNone(active_away(s, at))

    def test_overnight_uses_departure_day_and_wraps_week(self):
        s = away(full(), '22:00', '07:00', ['sun'])
        self.assertIsNone(active_away(s, london(utc(2026, 11, 15, 21, 59))))
        self.assertIsNotNone(active_away(s, london(utc(2026, 11, 15, 22))))
        self.assertIsNotNone(active_away(s, london(utc(2026, 11, 16, 6, 59))))
        self.assertIsNone(active_away(s, london(utc(2026, 11, 16, 7))))
        self.assertEqual(split_charge(s, utc(2026, 11, 15, 22), utc(2026, 11, 16, 7)), {})

    def test_away_overlap_and_dst_no_double_debit(self):
        s = away(full(), '00:00', '03:00', ['sun'])
        s['awayWindows'].append(dict(s['awayWindows'][0], id='overlap', start='01:00', end='02:00'))
        for month, day in [(3, 29), (10, 25)]:
            self.assertEqual(split_charge(s, utc(2026, month, day, 0), utc(2026, month, day, 2)), {})
        school(s)
        self.assertEqual(decide(s, london(utc(2026, 11, 16, 10)), 99999)['kind'], 'allow-exception')

    def test_roundtrip_and_invalid_schedules(self):
        base = school(away(full()))
        parsed, errors = validate_settings(json.loads(json.dumps(base)))
        self.assertEqual(errors, []); self.assertEqual(parsed, base)
        mutations = [lambda s: s['schoolHours'].update(enabled=1),
                     lambda s: s['schoolHours'].update(start='15:00', end='09:00'),
                     lambda s: s['schoolHours'].update(token='secret'),
                     lambda s: s['awayWindows'][0].update(days=[]),
                     lambda s: s['awayWindows'][0].update(start='08:00', end='08:00'),
                     lambda s: s['awayWindows'][0].update(end='bad'),
                     lambda s: s['awayWindows'][0].update(enabled='false'),
                     lambda s: s['awayWindows'].append(copy.deepcopy(s['awayWindows'][0])),
                     lambda s: s.update(awayWindows=[dict(s['awayWindows'][0], id=str(i)) for i in range(11)])]
        for mutate in mutations:
            raw = copy.deepcopy(base); mutate(raw)
            self.assertTrue(validate_settings(raw)[1], raw)
