import json
import unittest

from nettime.policy import decide, default_settings, init_tz, london, split_charge, validate_settings
from fakes import utc

init_tz()

DASHBOARD_EXPORT = """{
  "schemaVersion": 1, "timezone": "Europe/London", "deviceLabel": "iPad",
  "weekly": {"mon": 60, "tue": 60, "wed": 60, "thu": 60, "fri": 60, "sat": 120, "sun": 120},
  "exceptions": [{"id": "study", "label": "Study time", "days": ["sat", "sun"], "start": "11:00", "end": "12:00"}],
  "leisurePaused": false
}"""


def full():
    s, _ = validate_settings(json.loads(DASHBOARD_EXPORT))
    return s


class Import(unittest.TestCase):
    def test_dashboard_export_accepted(self):
        s, e = validate_settings(json.loads(DASHBOARD_EXPORT))
        self.assertEqual(e, [])
        self.assertEqual(s["weekly"]["sat"], 120)

    def test_rejects(self):
        base = json.loads(DASHBOARD_EXPORT)
        bad = []
        for mut in (lambda d: d.update(schemaVersion=2), lambda d: d.update(token="x"),
                    lambda d: d["weekly"].update(mon=1441), lambda d: d["weekly"].update(mon=True),
                    lambda d: d["weekly"].update(mon=1.5), lambda d: d["weekly"].pop("sun"),
                    lambda d: d["exceptions"][0].update(start="12:00", end="11:00"),
                    lambda d: d["exceptions"][0].update(days=[]), lambda d: d.update(timezone="UTC")):
            d = json.loads(json.dumps(base)); mut(d)
            bad.append(validate_settings(d)[1])
        self.assertTrue(all(bad))

    def test_unset_never_blocks(self):
        d = decide(default_settings(), london(utc(2026, 11, 16, 15)), 99999)
        self.assertIsNone(d["block"])


class Boundaries(unittest.TestCase):
    def kind(self, ts, used=0, paused=False):
        s = full(); s["leisurePaused"] = paused
        return decide(s, london(ts), used)["kind"]

    def test_saturday_sunday_gmt(self):  # 14/15 Nov 2026 are GMT
        for day in (14, 15):
            self.assertEqual(self.kind(utc(2026, 11, day, 10, 59), used=1e9), "block-exhausted")
            self.assertEqual(self.kind(utc(2026, 11, day, 11, 0), used=1e9, paused=True), "allow-exception")
            self.assertEqual(self.kind(utc(2026, 11, day, 11, 59, 59), used=1e9), "allow-exception")
            self.assertEqual(self.kind(utc(2026, 11, day, 12, 0), used=1e9), "block-exhausted")
            self.assertEqual(self.kind(utc(2026, 11, day, 12, 0), used=60), "allow-remaining")

    def test_bst(self):  # 13 Jun 2026 Sat, BST: 11:00 London = 10:00 UTC
        self.assertEqual(self.kind(utc(2026, 6, 13, 9, 59), used=1e9), "block-exhausted")
        self.assertEqual(self.kind(utc(2026, 6, 13, 10, 0), used=1e9), "allow-exception")
        self.assertEqual(self.kind(utc(2026, 6, 13, 11, 0), used=1e9), "block-exhausted")

    def test_weekday_has_no_exception(self):
        self.assertEqual(self.kind(utc(2026, 11, 16, 11, 30), used=1e9), "block-exhausted")

    def test_midnight_and_dst_dates(self):
        self.assertEqual(london(utc(2026, 6, 13, 22, 59))["date"], "2026-06-13")
        self.assertEqual(london(utc(2026, 6, 13, 23, 0))["date"], "2026-06-14")
        self.assertEqual(london(utc(2026, 3, 29, 1, 0))["minute"], 120)  # clocks go forward
        self.assertEqual(london(utc(2026, 10, 25, 1, 0))["minute"], 60)  # clocks go back


class Charging(unittest.TestCase):
    def test_split_midnight(self):
        r = split_charge(full(), utc(2026, 11, 16, 23, 59, 50), utc(2026, 11, 17, 0, 0, 5.5))
        self.assertAlmostEqual(r["2026-11-16"], 10)
        self.assertAlmostEqual(r["2026-11-17"], 5.5)

    def test_exception_not_charged(self):
        r = split_charge(full(), utc(2026, 11, 14, 10, 59, 50), utc(2026, 11, 14, 11, 0, 10))
        self.assertAlmostEqual(r["2026-11-14"], 10)
        r = split_charge(full(), utc(2026, 11, 14, 11, 59, 55), utc(2026, 11, 14, 12, 0, 7))
        self.assertAlmostEqual(r["2026-11-14"], 7)

    def test_dst_bst_midnight(self):
        r = split_charge(full(), utc(2026, 6, 16, 22, 59, 58), utc(2026, 6, 16, 23, 0, 3))
        self.assertEqual(sorted(r), ["2026-06-16", "2026-06-17"])
        self.assertAlmostEqual(sum(r.values()), 5)


if __name__ == "__main__":
    unittest.main()
