# Release numbering

This is NetTime 1.0.0, the first public planner and Raspberry Pi controller release. Public releases use 1.x.0 with a v-prefixed Git tag. The cross-platform release is 1.1.0; future releases increment the middle number, for example 1.2.0 and 1.3.0.

Keep the package, root lockfile and Python controller versions aligned. Rebuild the versioned ZIP after a version change and regenerate its SHA256SUMS.txt entry. Run scripts/check_release_version.py before publishing. Dependency and schedule-schema versions are independent.
