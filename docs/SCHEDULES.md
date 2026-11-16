# School hours and away periods

Use the live controller dashboard (not just the separate planner) to apply these rules. In the planner, save and export the settings, then import them into the controller. Settings do not sync automatically.

## School hours

Enable **School hours (Monday–Friday)** and enter the start/end times. School hours allow internet access and stop the allowance counting, even if no allowance remains or leisure access is paused. At the end, the existing allowance resumes; access is blocked if it is exhausted. School hours start disabled. Turn them off during holidays.

## Away from home

Choose **Add away period**, enter a name, select days and leave/return times, then save the schedule. Each period has an enabled switch and can be removed. Up to ten periods are supported. Away periods stop allowance counting; the normal block/allow decision still applies.

For an overnight period, select the departure day. Sunday 22:00–07:00 means Sunday night through Monday morning. A period with identical start/end times is invalid. School hours and ordinary exceptions stay within one day.

## Boundaries and overlaps

All times are Europe/London with automatic BST/GMT handling. Starts are included and ends excluded. Each interval is charged at most once; overlapping school, exception and away periods cannot duplicate time. Used time is preserved when a period ends, a setting changes or the controller restarts. Editing the schedule drops the previous sample interval rather than applying new rules retrospectively.

Policy order: incomplete setup makes no blocking decision; school hours and ordinary exceptions allow access; then manual leisure pause and the remaining daily allowance decide access. Away periods independently exclude time from charging. Changing schedules does not switch enforcement on.

These schedules do not detect screen locking or whether someone is physically home. Outside excluded periods, an idle connected-and-allowed device can still use allowance. The built-in Linksys integration continues to use a Wi-Fi MAC deny list; it can prevent rejoining Wi-Fi while blocked.

## Existing settings

Old settings load with school hours disabled and no away periods. New optional schemaVersion 1 fields are schoolHours (enabled, start, end) and awayWindows (id, label, enabled, days, start, end). Existing allowance, exceptions, credentials, usage and target are retained. New exports include both fields and are rejected by older programs; keep a private backup for rollback. Never publish the controller's private data directory.
