# Architecture

## Independent planner and controller

The React planner is a client-side Vite application with TanStack Router. A pure TypeScript policy function evaluates supplied settings, date, time and usage. The page does not invent a device connection or pretend to enforce a decision. Settings are versioned and validated before import.

The Python service has its own HTML/JavaScript dashboard. A polling worker reads the router while an HTTP server handles owner actions. Its standard-library implementation keeps the installation small enough for a Raspberry Pi; it has no Python package dependencies.

## Policy order

1. Incomplete or invalid settings prevent enforcement.
2. A matching exception permits access without charging time.
3. A leisure pause blocks outside exceptions.
4. The current day's allowance and bonus determine remaining access.

Exceptions are same-day intervals with an inclusive start and exclusive end. Cross-midnight windows are rejected. The timezone is currently Europe/London; it is not a configurable global-timezone system.

## Accounting

The engine charges only intervals for which the selected Wi-Fi address is reported connected and internet is allowed. Intervals are split at exception and London-day boundaries. A stale or malformed router response is unknown, not an offline device. Downtime and clock jumps are not filled with estimated usage.

This measures internet-enabled connection time, including idle background activity, rather than screen interaction. It cannot identify YouTube, games or any other individual application.

## Router transaction boundary

The JNAP adapter supports a narrow MAC-filter API. It reads the current list, checks the saved state, writes a single device's entry while preserving other entries, then verifies the result by reading again. It requires Deny mode and never switches modes automatically.

The state records ownership and pending changes. A lost response does not justify another automatic write. Manual changes or an unconfirmed operation pause automation until the owner reviews the router. On restart, saved enforcement is revalidated before automation resumes.

## Trust boundaries

| Boundary | Control | Remaining limitation |
| --- | --- | --- |
| Browser to Pi | SSH tunnel, loopback listener, API access key, Host/Origin checks | The owner must protect the Pi account and access key |
| Pi to router | Pinned HTTPS certificate | Initial pin verification is the owner's trust decision |
| Local persistence | Restricted permissions and atomic file replacement | Router authentication remains readable by that OS account |
| Router to client | One selected MAC-filter entry | MAC changes and other networks can bypass it |

## Validation approach

TypeScript tests cover policy evaluation, validation, browser persistence and bonus-date scoping. Python tests use fake routers and clocks to exercise error paths that are difficult to reproduce safely on real equipment. The package tests verify reproducibility, credential exclusions and installation through a mocked service manager.

The public distribution deliberately omits private deployment records, provider project metadata, historical binary packages and an unrelated radio experiment. Only sanitised source and a newly built controller package are published.
