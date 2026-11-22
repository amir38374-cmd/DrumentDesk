#!/usr/bin/env python3
"""
DrumentDesk branding patch.

Runs inside the GitHub Actions build, right after the source is checked out.
It changes the app name, the built-in server + key, and a few visible strings.

It FAILS LOUDLY (exit code 1) if any expected line is missing, so a wrong patch
is caught in the first minute instead of after a long build.

Environment variables (come from GitHub Secrets):
  RENDEZVOUS_SERVER   your server address, e.g. 87.107.190.211
  RS_PUB_KEY          your server public key (contents of id_ed25519.pub)
"""
import os
import pathlib
import re
import sys

APP = "DrumentDesk"
errors = []


def read(path):
    return pathlib.Path(path).read_bytes().decode("utf-8")


def write(path, text):
    pathlib.Path(path).write_bytes(text.encode("utf-8"))


def patch(path, old, new, expected=1, regex=False, flags=0):
    if not pathlib.Path(path).exists():
        errors.append(f"{path}: file not found")
        return
    text = read(path)
    if regex:
        new_text, n = re.subn(old, new, text, flags=flags)
    else:
        n = text.count(old)
        new_text = text.replace(old, new)
    if n != expected:
        errors.append(f"{path}: expected {expected} match(es) of {old[:70]!r}, found {n}")
        return
    write(path, new_text)
    print(f"ok  {path}: {n} change(s)")


# ---------------------------------------------------------------- server + key
server = os.environ.get("RENDEZVOUS_SERVER", "").strip()
key = os.environ.get("RS_PUB_KEY", "").strip()

if not re.fullmatch(r"[A-Za-z0-9.\-]{3,253}", server):
    errors.append("RENDEZVOUS_SERVER secret is missing or has an invalid value")
if not re.fullmatch(r"[A-Za-z0-9+/]{43}=", key):
    errors.append("RS_PUB_KEY secret is missing or is not a valid 44-character key")

CONFIG = "libs/hbb_common/src/config.rs"
if not errors:
    # app name
    patch(CONFIG, 'RwLock::new("RustDesk".to_owned())', f'RwLock::new("{APP}".to_owned())')
    # built-in server and key
    patch(
        CONFIG,
        r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\["[^"]*"\];',
        f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{server}"];',
        regex=True,
    )
    patch(
        CONFIG,
        r'pub const RS_PUB_KEY: &str = "[^"]*";',
        f'pub const RS_PUB_KEY: &str = "{key}";',
        regex=True,
    )

# ---------------------------------------------------------------- Windows exe info
RC = "flutter/windows/runner/Runner.rc"
patch(RC, 'VALUE "FileDescription", "RustDesk Remote Desktop"', f'VALUE "FileDescription", "{APP} Remote Desktop"')
patch(RC, 'VALUE "InternalName", "rustdesk"', f'VALUE "InternalName", "{APP.lower()}"')
patch(RC, 'VALUE "OriginalFilename", "rustdesk.exe"', f'VALUE "OriginalFilename", "{APP.lower()}.exe"')
patch(RC, 'VALUE "ProductName", "RustDesk"', f'VALUE "ProductName", "{APP}"')
patch("flutter/windows/runner/main.cpp", 'std::wstring app_name = L"RustDesk";', f'std::wstring app_name = L"{APP}";')

# ---------------------------------------------------------------- visible UI strings
# title next to the icon in the window title bar
patch(
    "flutter/lib/desktop/widgets/tabbar_widget.dart",
    r'"RustDesk",(\s*style: TextStyle\(fontSize: 13\),)',
    rf'"{APP}",\1',
    regex=True,
)
# "Powered by ..." footer: always hidden
patch(
    "flutter/lib/common.dart",
    """if (bind.mainGetBuildinOption(key: "hide-powered-by-me") == 'Y') {""",
    "if (true) {",
)
# About page: remove the two links that point to the original website
# and keep the license notice (required by the AGPL license).
ABOUT = "flutter/lib/desktop/pages/desktop_setting_page.dart"
patch(
    ABOUT,
    r"InkWell\(\s*onTap: \(\) \{\s*launchUrlString\('https://rustdesk\.com(?:/privacy\.html)?'\);\s*\},\s*child: Text\(\s*translate\('(?:Privacy Statement|Website)'\),\s*style: linkStyle,\s*\)\.marginSymmetric\(vertical: 4\.0\)\),",
    "",
    expected=2,
    regex=True,
)
patch(
    ABOUT,
    r"Purslane Tech Pte. Ltd.\n$license',",
    r"Purslane Tech Pte. Ltd.\n$license\nBased on open-source RustDesk (AGPL-3.0).',",
)
# small visible strings
patch("src/platform/windows.rs", '"RustDesk Output"', f'"{APP} Output"')
patch("src/whiteboard/windows.rs", '"RustDesk whiteboard"', f'"{APP} whiteboard"')
patch("src/auth_2fa.rs", 'const ISSUER: &str = "RustDesk";', f'const ISSUER: &str = "{APP}";')

if errors:
    print("\nBRANDING FAILED:", file=sys.stderr)
    for e in errors:
        print("  -", e, file=sys.stderr)
    sys.exit(1)
print("\nBranding applied.")
