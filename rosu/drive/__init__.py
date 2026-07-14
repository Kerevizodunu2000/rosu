# SPDX-License-Identifier: GPL-3.0-or-later
"""Google Drive backup + cross-device store (item 11, v0.8).

Kept import-light on purpose: submodules pull in keyring / urllib / http.server
only when actually used, so app startup and ``--selftest`` never touch the
network or the OS keyring. ``manifest`` and ``bundle`` are pure stdlib and safe
to import anywhere; ``auth`` and ``client`` do the online work.
"""
