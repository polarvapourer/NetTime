import json
import shutil
import tempfile
import unittest

from nettime.engine import Engine, UserError
from nettime.policy import init_tz, validate_settings
from nettime.router import RouterError
from nettime.store import Store
from fakes import IPAD, NODE, OTHER, PI, Clock, make_router, utc
from test_policy import DASHBOARD_EXPORT

init_tz()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(self.dir)
        self.clock = Clock(utc(2026, 11, 16, 15, 0))  # Monday, GMT
        self.r, self.t = make_router(macs=[OTHER])
        self.e = self.new_engine()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def new_engine(self):
        return Engine(self.store, self.r, clock=self.clock.wall, mono=self.clock.mono, self_macs={PI})

    def configure(self, minutes=1):
        s = json.loads(DASHBOARD_EXPORT)
        for d in s["weekly"]:
            s["weekly"][d] = minutes
        self.e.save_settings(s)
        self.e.discover()
        self.e.select_target(IPAD, "iPad")

    def run_for(self, seconds, step=10):
        for _ in range(int(seconds // step)):
            self.clock.advance(step)
            self.e.tick()


class Observation(Base):
    def test_zero_writes_and_no_counting(self):
        self.configure()
        self.run_for(600)
        self.assertEqual(self.t.writes(), [])
        snap = self.e.snapshot()
        self.assertTrue(snap["observationOnly"])
        self.assertEqual(snap["today"]["usedSeconds"], 0)
        self.assertEqual(snap["status"]["connection"], "connected")

    def test_import_and_restart_never_enable(self):
        self.configure()
        self.assertFalse(self.e.snapshot()["enforcement"])
        self.assertFalse(self.new_engine().snapshot()["enforcement"])


class Activation(Base):
    def test_refusals(self):
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)  # nothing configured
        self.e.discover()
        for bad in (PI, NODE):
            with self.assertRaises(UserError):
                self.e.select_target(bad)
        self.configure()
        self.t.mode = "Allow"
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)
        self.t.mode = "Deny"
        self.t.macs.append(IPAD)  # manual block present
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)
        self.assertEqual(self.t.writes(), [])

    def test_incomplete_schedule_refused(self):
        self.e.discover(); self.e.select_target(IPAD)
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)


class Enforcement(Base):
    def test_counts_blocks_and_preserves(self):
        self.configure(minutes=1)
        self.e.tick()
        self.e.set_enforcement(True)
        self.run_for(50)
        self.assertEqual(self.t.writes(), [])
        self.run_for(20)
        self.assertEqual(len(self.t.writes()), 1)
        self.assertEqual(self.t.macs, [OTHER, IPAD])
        self.assertEqual(self.e.snapshot()["status"]["rule"], "confirmed")
        used = self.e.snapshot()["today"]["usedSeconds"]
        self.run_for(100)
        self.assertEqual(self.e.snapshot()["today"]["usedSeconds"], used)  # blocked: not counted

    def test_external_unblock_pauses_without_undo(self):
        self.configure(minutes=0)
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(10)
        self.assertIn(IPAD, self.t.macs)
        self.t.macs.remove(IPAD)  # another administrator unblocks in the router app
        self.run_for(60)
        self.assertNotIn(IPAD, self.t.macs)
        self.assertEqual(len(self.t.writes()), 1)
        self.assertIn("outside NetTime", self.e.snapshot()["paused"])

    def test_mode_change_pauses(self):
        self.configure(minutes=0)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.t.mode = "Allow"
        self.run_for(30)
        self.assertTrue(self.e.snapshot()["paused"])
        self.assertEqual(len(self.t.writes()), 1)

    def test_disable_releases_only_own_block(self):
        self.configure(minutes=0)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.e.set_enforcement(False)
        self.assertEqual(self.t.macs, [OTHER])

    def test_study_allows_without_debit_then_noon_blocks(self):
        self.clock.t = utc(2026, 11, 14, 10, 59, 0)  # Saturday GMT
        self.configure(minutes=0)
        s = self.e.snapshot()["settings"]; s["leisurePaused"] = True; self.e.save_settings(s)
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(30)
        self.assertIn(IPAD, self.t.macs)
        self.run_for(60)   # 11:00 -> unblock, even paused & exhausted
        self.assertNotIn(IPAD, self.t.macs)
        self.run_for(3600)  # through to 12:00:30
        self.assertIn(IPAD, self.t.macs)
        self.assertLess(self.e.snapshot()["today"]["usedSeconds"], 1)

    def test_unknown_gaps_and_errors_not_charged(self):
        self.configure(minutes=600)
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(100)
        u = self.e.snapshot()["today"]["usedSeconds"]
        self.assertAlmostEqual(u, 90)  # first sample after switch-on has no previous sample
        self.clock.advance(300); self.e.tick()  # gap > 30s: not charged
        self.assertAlmostEqual(self.e.snapshot()["today"]["usedSeconds"], u)
        self.t.fail["GetMACFilterSettings"] = RouterError("network", "x")
        self.run_for(30)
        self.assertEqual(self.e.snapshot()["status"]["metering"], "unknown")
        del self.t.fail["GetMACFilterSettings"]
        self.run_for(10)
        self.assertAlmostEqual(self.e.snapshot()["today"]["usedSeconds"], u)

    def test_offline_not_charged(self):
        self.configure(minutes=600)
        self.t.ipad_online = False
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(100)
        self.assertEqual(self.e.snapshot()["status"]["connection"], "not-connected")
        self.assertEqual(self.e.snapshot()["today"]["usedSeconds"], 0)

    def test_clock_rollback_no_double_count(self):
        self.configure(minutes=600)
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(60)
        u = self.e.snapshot()["today"]["usedSeconds"]
        self.clock.advance(-60, wall_only=True); self.clock.m += 10; self.e.tick()
        self.run_for(50)
        self.assertAlmostEqual(self.e.snapshot()["today"]["usedSeconds"], u)

    def test_restart_keeps_usage_and_drops_stale_bonus(self):
        self.configure(minutes=600)
        self.e.add_bonus(30)
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(60)
        u = self.e.snapshot()["today"]["usedSeconds"]
        e2 = self.new_engine()
        self.assertAlmostEqual(e2.snapshot()["today"]["usedSeconds"], u)
        self.assertEqual(e2.snapshot()["today"]["bonusMinutes"], 30)
        self.clock.t = utc(2026, 11, 17, 0, 0, 5)
        self.assertEqual(e2.snapshot()["today"]["bonusMinutes"], 0)
        self.assertEqual(e2.snapshot()["today"]["usedSeconds"], 0)

    def test_midnight_new_quota(self):
        self.clock.t = utc(2026, 11, 16, 23, 59, 0)
        self.configure(minutes=0)
        s = self.e.snapshot()["settings"]; s["weekly"]["tue"] = 60; self.e.save_settings(s)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.assertIn(IPAD, self.t.macs)
        self.run_for(60)
        self.assertNotIn(IPAD, self.t.macs)


class Review(Base):
    def enabled_blocked(self):
        self.configure(minutes=0)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.assertIn(IPAD, self.t.macs)

    def test_only_selected_mac_counts_as_connected(self):
        self.e.st["target"] = IPAD
        self.assertEqual(self.e._connection([{"macs": [IPAD, OTHER], "online": True, "connectedMacs": [OTHER]}]), "not-connected")
        self.assertEqual(self.e._connection([{"macs": [IPAD], "online": True, "connectedMacs": [IPAD]}]), "connected")

    def test_failed_write_pauses_and_never_repeats(self):
        self.configure(minutes=0)
        self.t.set_applies = False
        self.e.tick(); self.e.set_enforcement(True)
        self.run_for(60)
        self.assertEqual(len(self.t.writes()), 1)
        snap = self.e.snapshot()
        self.assertIn("Rule uncertain", snap["paused"])
        self.assertEqual(snap["pending"]["want"], True)
        self.assertTrue(snap["observationOnly"])
        self.assertTrue(self.new_engine().snapshot()["paused"])  # persists across restart

    def test_external_unblock_during_uncertainty_not_undone(self):
        self.configure(minutes=0)
        self.t.fail_get_after_set = True  # write applies, readback times out
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.assertIn(IPAD, self.t.macs)
        self.assertIn("uncertain", self.e.snapshot()["paused"])
        self.t.macs.remove(IPAD)
        self.run_for(60)
        self.assertEqual(len(self.t.writes()), 1)
        self.assertNotIn(IPAD, self.t.macs)
        self.assertEqual(self.e.resume(), "Router checked; automation resumed")
        self.assertFalse(self.e.snapshot()["ownedBlock"])

    def test_uncertain_write_that_applied_is_owned_after_reconcile(self):
        self.configure(minutes=0)
        self.t.fail_get_after_set = True
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.e.resume()
        self.assertTrue(self.e.snapshot()["ownedBlock"])
        self.e.set_enforcement(False)
        self.assertNotIn(IPAD, self.t.macs)

    def uncertain_add_then_stop(self):
        self.configure(minutes=0)
        self.t.fail_get_after_set = True  # block write applies, readback fails
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.t.fail_get_after_set = False
        snap = self.e.snapshot()
        self.assertTrue(snap["pending"]["want"]); self.assertFalse(snap["ownedBlock"])
        msg = self.e.set_enforcement(False)
        self.assertIn("may remain", msg)
        return msg

    def test_stop_during_uncertain_add_keeps_marker(self):
        self.uncertain_add_then_stop()
        for e in (self.e, self.new_engine()):
            snap = e.snapshot()
            self.assertFalse(snap["enforcement"])
            self.assertTrue(snap["pending"]["want"])
            self.assertTrue(snap["releaseAttention"])
        n = len(self.t.writes())
        self.run_for(60)
        self.assertEqual(len(self.t.writes()), n)  # no automatic writes
        self.assertIn(IPAD, self.t.macs)
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)

    def test_uncertain_block_needs_explicit_confirmation(self):
        self.uncertain_add_then_stop()
        n = len(self.t.writes())
        self.assertIn("may be NetTime's block or a manual one", self.e.retry_release())
        self.assertEqual(len(self.t.writes()), n)
        self.assertIn(IPAD, self.t.macs)
        self.assertIn("removed", self.e.retry_release(confirm_uncertain=True))
        self.assertEqual(self.t.macs, [OTHER])
        self.assertIsNone(self.e.snapshot()["pending"])

    def test_confirm_without_fresh_check_does_not_remove(self):
        self.uncertain_add_then_stop()
        self.e.retry_release(confirm_uncertain=True)  # first call only reads
        self.assertIn(IPAD, self.t.macs)

    def test_uncertain_marker_cleared_when_router_shows_no_block(self):
        self.uncertain_add_then_stop()
        self.t.macs.remove(IPAD)
        n = len(self.t.writes())
        self.assertIn("not in the deny list", self.e.retry_release())
        self.assertEqual(len(self.t.writes()), n)
        self.assertFalse(self.e.snapshot()["releaseAttention"])

    def test_disable_with_router_down_is_durable_and_retryable(self):
        self.enabled_blocked()
        self.t.fail["GetMACFilterSettings"] = RouterError("network", "x")
        msg = self.e.set_enforcement(False)
        self.assertIn("may remain", msg)
        self.assertFalse(self.new_engine().snapshot()["enforcement"])
        self.assertTrue(self.e.snapshot()["ownedBlock"])
        self.run_for(30)
        self.assertEqual(len(self.t.writes()), 1)  # stopped: no scheduling
        del self.t.fail["GetMACFilterSettings"]
        self.assertIn("removed", self.e.retry_release())
        self.assertNotIn(IPAD, self.t.macs)

    def test_ambiguous_release_keeps_ownership(self):
        self.enabled_blocked()
        self.t.set_applies = False
        self.assertIn("may remain", self.e.set_enforcement(False))
        self.assertTrue(self.e.snapshot()["ownedBlock"])
        self.t.set_applies = True
        self.e.retry_release()
        self.assertEqual(self.t.macs, [OTHER])

    def test_manual_block_never_released_on_disable(self):
        self.configure(minutes=600)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.e.set_enforcement(False)
        self.t.macs.append(IPAD)
        self.assertEqual(self.e.retry_release(), "No NetTime block to remove")
        self.assertIn(IPAD, self.t.macs)

    def test_restart_resumes_after_validation(self):
        self.enabled_blocked()
        e2 = self.new_engine(); self.e = e2
        self.run_for(30)
        self.assertIsNone(e2.snapshot()["paused"])
        self.assertTrue(e2.snapshot()["enforcement"])
        self.assertEqual(len(self.t.writes()), 1)

    def test_restart_after_offline_override_pauses(self):
        self.enabled_blocked()
        self.t.macs.remove(IPAD)  # another administrator unblocks while the Pi is off
        e2 = self.new_engine(); self.e = e2
        self.run_for(30)
        self.assertIn("after restart", e2.snapshot()["paused"])
        self.assertEqual(len(self.t.writes()), 1)

    def test_restart_with_target_now_router_node_pauses(self):
        self.enabled_blocked()
        e2 = Engine(self.store, self.r, clock=self.clock.wall, mono=self.clock.mono, self_macs={PI, IPAD})
        self.e = e2
        self.run_for(10)
        self.assertTrue(e2.snapshot()["paused"])
        self.assertEqual(len(self.t.writes()), 1)

    def test_fresh_engine_with_disabled_state_stays_off(self):
        self.configure(minutes=0)
        e2 = self.new_engine(); self.e = e2
        self.run_for(30)
        self.assertFalse(e2.snapshot()["enforcement"])
        self.assertEqual(self.t.writes(), [])

    def test_study_label_not_counting(self):
        self.clock.t = utc(2026, 11, 14, 11, 10)
        self.configure(minutes=600)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(60)
        snap = self.e.snapshot()
        self.assertEqual(snap["status"]["metering"], "exception")
        self.assertEqual(snap["today"]["usedSeconds"], 0)

    def test_malformed_device_list_unknown_no_meter_no_write(self):
        self.configure(minutes=600)
        self.e.tick(); self.e.set_enforcement(True); self.run_for(20)
        u = self.e.snapshot()["today"]["usedSeconds"]
        self.t.result["GetDevices3"] = {"result": "OK", "output": {"devices": [{"deviceID": "ipad", "knownInterfaces": []}]}}
        self.run_for(60)
        snap = self.e.snapshot()
        self.assertEqual(snap["status"]["connection"], "unknown")
        self.assertEqual(snap["status"]["connectionStale"], "connected")
        self.assertEqual(snap["today"]["usedSeconds"], u)
        self.assertEqual(self.t.writes(), [])


class Unselect(Base):
    def setup_counted(self):
        self.configure(minutes=60)
        self.e.add_bonus(15)
        self.run_for(60)  # observation: status populated
        self.e.tick()

    def test_clear_persists_without_router_contact_and_keeps_counters(self):
        self.setup_counted()
        self.st_before = json.loads(json.dumps(self.e.st))
        posts = len(self.t.posts)
        self.t.fail["GetMACFilterSettings"] = RouterError("timeout", "down")  # router unavailable
        self.e.clear_target()
        self.assertEqual(len(self.t.posts), posts)  # no router contact at all
        snap = self.e.snapshot()
        self.assertIsNone(snap["target"]); self.assertIsNone(snap["targetName"])
        self.assertEqual(snap["status"]["connection"], "unknown")
        self.assertIsNone(snap["status"]["targetInList"])
        self.assertIsNone(snap["status"]["ruleMessage"])
        self.assertIsNone(self.e.last_sample)
        self.assertIn("Select the device from the device list", snap["activationProblems"])
        for k in ("settings", "usage", "bonus", "enforcement", "ownedBlock", "pending"):
            self.assertEqual(self.e.st[k], self.st_before[k], k)
        r = self.new_engine()  # restart
        self.assertIsNone(r.snapshot()["target"]); self.assertIsNone(r.snapshot()["targetName"])
        self.assertEqual(r.st["usage"], self.st_before["usage"])
        self.assertEqual(self.t.writes(), [])

    def test_idempotent_and_no_target_activation_refused(self):
        self.e.clear_target(); self.e.clear_target()
        self.configure(); self.e.clear_target(); self.e.clear_target()
        with self.assertRaises(UserError):
            self.e.set_enforcement(True)
        self.assertFalse(self.e.snapshot()["enforcement"])
        self.assertEqual(self.t.writes(), [])

    def test_refused_while_enabled(self):
        self.configure(minutes=60); self.e.tick(); self.e.set_enforcement(True)
        with self.assertRaises(UserError):
            self.e.clear_target()
        self.assertEqual(self.e.st["target"], IPAD)
        self.assertEqual(self.new_engine().st["target"], IPAD)

    def test_refused_with_owned_block_and_replacement_guarded(self):
        self.configure(minutes=0); self.e.tick(); self.e.set_enforcement(True); self.run_for(10)
        self.t.fail["SetMACFilterSettings"] = RouterError("timeout", "down")
        self.e.set_enforcement(False)  # release fails: ownership kept
        self.assertTrue(self.e.st["ownedBlock"])
        with self.assertRaises(UserError):
            self.e.clear_target()
        with self.assertRaises(UserError):
            self.e.select_target(OTHER)
        self.assertEqual(self.e.st["target"], IPAD)
        self.assertTrue(self.e.st["ownedBlock"])
        self.assertIn(IPAD, self.t.macs)  # nothing removed silently

    def test_refused_with_any_pending_marker(self):
        self.configure(minutes=60)
        for pend in ({"want": True, "status": "present-unverified", "at": 1}, {"want": False, "status": "unknown", "at": 1}):
            self.e.st["pending"] = pend; self.e._save()
            e = self.new_engine(); e.discover()
            with self.assertRaises(UserError):
                e.clear_target()
            with self.assertRaises(UserError):
                e.select_target(OTHER)
            self.assertEqual(e.st["target"], IPAD)
            self.assertEqual(e.st["pending"], pend)
        self.assertEqual(self.t.writes(), [])

    def test_reselect_after_clear_resets_old_status(self):
        self.configure(); self.run_for(30)
        self.e.clear_target(); self.e.discover(); self.e.select_target(IPAD, "iPad")
        self.assertEqual(self.e.snapshot()["status"]["connection"], "unknown")



if __name__ == "__main__":
    unittest.main()
