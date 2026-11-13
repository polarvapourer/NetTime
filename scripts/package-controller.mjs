// Use the host's native Python; the package itself has no CPU-specific binaries.
import { spawnSync } from "node:child_process";
const candidates = process.platform === "win32" ? [["py", "-3"], ["python"], ["python3"]] : [["python3"], ["python"]];
for (const [command, ...prefix] of candidates) {
  const probe = spawnSync(command, [...prefix, "-c", "import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)"], { stdio: "ignore" });
  if (probe.status !== 0) continue;
  const result = spawnSync(command, [...prefix, "scripts/build_controller_zip.py"], { stdio: "inherit" });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}
console.error("Install Python 3, then run npm run package:controller again.");
process.exit(1);
