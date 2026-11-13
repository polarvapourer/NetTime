"""Browser checks for the Pi page states (mocked API, no Pi/router). Run: python3 scripts/pi_ui_states.py"""
import asyncio, copy, json
from pathlib import Path
from playwright.async_api import async_playwright

STATIC = Path(__file__).resolve().parent.parent / "controller/nettime/static"
BASE = {
    "status": {"router": "ok", "lastSuccess": 1794500000, "lastError": None, "mode": "Deny", "targetInList": True,
               "connection": "connected", "connectionStale": None, "metering": "counting", "exceptionLabel": None, "ruleMessage": None},
    "settings": {"weekly": {d: 60 for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
                 "exceptions": [{"label": "Study time", "days": ["sat", "sun"], "start": "11:00", "end": "12:00"}], "leisurePaused": False},
    "target": "aa:bb:cc:00:00:01", "targetName": "iPad", "enforcement": False, "paused": None, "pending": None,
    "ownedBlock": False, "releaseAttention": False, "observationOnly": True,
    "today": {"date": "2026-11-12", "day": "thu", "minute": 1230, "usedSeconds": 600, "bonusMinutes": 0,
              "decision": {"label": "Allowed"}}, "activationProblems": []}

def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond: raise SystemExit(1)

async def main():
    st = {"snap": copy.deepcopy(BASE), "down": False, "release": [], "cleared": 0}
    async def handle(route, req):
        path = req.url.split("8799", 1)[1].split("?")[0]
        if path.startswith("/api/"):
            if st["down"]: return await route.abort("connectionrefused")
            if path == "/api/release":
                body = json.loads(req.post_data or "{}"); st["release"].append(body)
                st["snap"].update(ownedBlock=False, pending=None, releaseAttention=False)
                return await route.fulfill(json={"message": "NetTime's block removed and confirmed."})
            if path == "/api/target/clear":
                st["cleared"] += 1
                st["snap"].update(target=None, targetName=None)
                st["snap"]["status"].update(connection="unknown", targetInList=None)
                return await route.fulfill(json={"message": "Device unselected. Blocking stays off."})
            if path == "/api/target":
                body = json.loads(req.post_data or "{}")
                st["snap"].update(target=body["mac"], targetName=body["name"])
                return await route.fulfill(json={"message": "Device selected"})
            if path == "/api/discover":
                return await route.fulfill(json={"devices": [{"name": "iPad", "addresses": [
                    {"mac": "aa:bb:cc:00:00:01", "connected": False, "reason": None},
                    {"mac": "aa:bb:cc:00:00:02", "connected": True, "reason": None}]}]})
            return await route.fulfill(json=st["snap"])
        f = STATIC / ("index.html" if path in ("/", "") else path.lstrip("/").split("/", 1)[-1])
        if not f.exists(): f = STATIC / path.lstrip("/")
        ct = {"js": "text/javascript", "css": "text/css"}.get(f.suffix[1:], "text/html")
        await route.fulfill(body=f.read_bytes(), content_type=ct)
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await (await b.new_context(viewport={"width": 1280, "height": 1800})).new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await page.route("http://pi.test:8799/**", handle)
        await page.goto("http://pi.test:8799/#key=test")
        await page.wait_for_selector("#app:not([hidden])")
        txt = lambda sel: page.locator(sel).inner_text()
        check("(London)" in await txt("#status"), "last success shown in London time")
        # paused with server reason
        st["snap"].update(paused="Router change refused. Check the router.")
        await page.evaluate("1"); await page.click("#save"); await page.wait_for_timeout(300)
        check(await txt("#mode-pill") == "Automation paused", "pill is generic 'Automation paused'")
        check("Router change refused" in await txt("#paused"), "actual pause reason shown")
        check("outside NetTime" not in await page.content(), "no assumed external cause")
        # exception + stale
        st["snap"]["paused"] = None
        st["snap"]["status"].update(metering="exception", exceptionLabel="Study time", connection="unknown", connectionStale="connected")
        await page.click("#save"); await page.wait_for_timeout(300)
        s = await txt("#status")
        check("Study time exception — time not counted" in s, "exception label rendered")
        check("last known: Router reports this address connected, stale" in s, "stale last-known shown")
        # per-MAC discovery rows
        await page.click("#discover"); await page.wait_for_timeout(300)
        rows = await page.locator("#devices .dev").all_inner_texts()
        check("00:01 · not connected" in rows[0] and "00:02 · connected" in rows[1], "per-address connected flags")
        # release prompt
        check(await page.locator("#release-btn").is_hidden(), "release hidden when nothing to remove")
        st["snap"].update(pending={"want": True, "status": "present-unverified"}, releaseAttention=True)
        await page.click("#save"); await page.wait_for_timeout(300)
        check(await txt("#release-btn") == "Remove uncertain block", "uncertain block button shown")
        await page.click("#release-btn"); await page.wait_for_timeout(400)
        check(st["release"] == [{"confirmUncertain": True}], "click reached /api/release with confirmation")
        check(await page.locator("#release-btn").is_hidden(), "prompt gone after confirmed release")
        # unselect device: guarded, then cleared without rediscovery; rows refresh
        st["snap"].update(enforcement=True)
        await page.click("#save"); await page.wait_for_timeout(300)
        check(await page.locator("#unselect-btn").is_disabled() and "Switch blocking off" in await txt("#unselect-why"), "unselect disabled while blocking on")
        st["snap"].update(enforcement=False, ownedBlock=True)
        await page.click("#save"); await page.wait_for_timeout(300)
        check(await page.locator("#unselect-btn").is_disabled() and "unresolved" in await txt("#unselect-why"), "unselect disabled with unresolved block")
        st["snap"].update(ownedBlock=False)
        await page.click("#save"); await page.wait_for_timeout(300)
        check("Selected: iPad" in await txt("#sel-summary") and not await page.locator("#unselect-btn").is_disabled(), "selected summary + enabled unselect")
        check((await page.locator("#devices .dev button").all_inner_texts())[0] == "Selected", "row shows Selected")
        await page.click("#unselect-btn"); await page.wait_for_timeout(400)
        check(st["cleared"] == 1, "unselect reached /api/target/clear")
        check(await txt("#sel-summary") == "No device selected" and await page.locator("#unselect-btn").is_hidden(), "no-selection display")
        check("Not selected" in await txt("#status"), "status shows not selected")
        check((await page.locator("#devices .dev button").all_inner_texts()) == ["Select", "Select"], "rows refreshed to Select")
        await page.locator("#devices .dev button").nth(1).click(); await page.wait_for_timeout(400)
        check((await page.locator("#devices .dev button").all_inner_texts()) == ["Select", "Selected"], "new selection reflected in rows")
        await page.screenshot(path="/tmp/browser/pi/selected.png")
        # connection lost then recovery, unsaved input kept
        await page.fill("#day-mon", "42")
        st["down"] = True
        await page.evaluate("1"); await page.click("#bonus-clear"); await page.wait_for_timeout(400)
        check(not await page.locator("#lost").is_hidden(), "connection lost notice shown")
        check(await txt("#mode-pill") == "Pi connection unknown", "pill shows connection unknown")
        check(await page.locator("#save").is_disabled() and await page.locator("#enf-btn").is_disabled(), "controls disabled")
        check(await page.locator("#unselect-btn").is_disabled() and await page.locator("#devices .dev button").first.is_disabled(), "unselect and rows disabled when Pi lost")
        await page.screenshot(path="/tmp/browser/pi/lost.png")
        st["down"] = False
        await page.wait_for_timeout(10500)
        check(await page.locator("#lost").is_hidden(), "notice cleared on reconnect")
        check(not await page.locator("#save").is_disabled(), "controls restored")
        check(not await page.locator("#unselect-btn").is_disabled(), "unselect restored")
        check(await page.input_value("#day-mon") == "42", "unsaved editor input kept")
        await b.close()

asyncio.run(main())
