# Release numbering

Public NetTime releases use **1.x.0**. The tag adds a `v`: `v1.0.0`, `v1.1.0`, `v1.2.0`, `v1.3.0`, and so on. Increment the middle number for every new release; keep the first number at 1 and the last at 0.

The initial public Raspberry Pi release is **1.0.0**. The cross-platform controller and router-adapter release is **1.1.0**. Their former names were 0.2.0 and 0.3.0 respectively. Legacy source tags are retained as historical references; use the 1.x.0 release pages for current downloads.

## Checklist

1. Choose the next unused `1.x.0` version.
2. Set the same version in `package.json`, both root version fields in `package-lock.json`, and `controller/nettime/__init__.py`. Do not alter dependency or schedule-schema versions.
3. Update the controller README, setup guide, planner download link, root README and changelog. Check any release-specific source links.
4. Run `python3 scripts/check_release_version.py` (`py -3` on Windows). CI runs this check too.
5. Rebuild with `npm run package:controller`, or the documented Python builder. Verify the ZIP's internal version and the generated `SHA256SUMS.txt` against the versioned download.
6. Run the controller/planner checks and verify CI for the exact source commit. Do not include private controller configuration or credentials.
7. Publish tag `v1.x.0` at that commit and attach the matching package and checksum. Use a GitHub no-reply address for commit author/committer metadata. Mark the newest release as latest; maintenance of an older release must not change that choice.
8. Verify the public download and checksum, and that the source archive, program version and release title agree.

Renumbering an existing release requires rebuilding version-bearing packages and updating their checksums as well as the visible title. Keep the feature scope of older releases intact.
