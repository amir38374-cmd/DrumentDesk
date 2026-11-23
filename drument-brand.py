#!/usr/bin/env python3
"""
DruDesk branding patch.

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

APP = "DruDesk"
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
# ---------------------------------------------------------------- colors (match the Drument login page)
COMMON = "flutter/lib/common.dart"
patch(COMMON, "Color(0xFF0071FF)", "Color(0xFF2FB393)")   # accent
patch(COMMON, "Color(0x770071FF)", "Color(0x772FB393)")   # accent50
patch(COMMON, "Color(0xAA0071FF)", "Color(0xAA2FB393)")   # accent80
patch(COMMON, "Color(0xFF2C8CFF)", "Color(0xFF2FB393)", expected=2)  # button colors
patch(COMMON, r"primary: Colors\.blue,(\s*)secondary: accent", r"primary: accent,\1secondary: accent", expected=2, regex=True)
# ---------------------------------------------------------------- design (dark navy look like the Drument site)
patch(COMMON, "Color(0xFF18191E)", "Color(0xFF0B1220)", expected=2)   # window / dialog background
patch(COMMON, "Color(0xFF24252B)", "Color(0xFF111A2B)", expected=5)   # cards, panels, input fields
patch(COMMON, "Color(0xFF00B6F0)", "Color(0xFF2FB393)")               # ID color
patch(COMMON, "BorderRadius.circular(8.0)", "BorderRadius.circular(14.0)", expected=5)
patch(COMMON, "BorderRadius.circular(8)", "BorderRadius.circular(14)", expected=3)
# default theme = dark (still changeable in Settings -> General)
patch(
    COMMON,
    r"default:\s*return ThemeMode\.system;",
    'case "system":\n        return ThemeMode.system;\n      default:\n        return ThemeMode.dark;',
    regex=True,
)
# never show the "set up your own server" tip (this build already uses your server)
patch(
    "src/common.rs",
    r'(pub fn using_public_server\(\) -> bool \{\s*)crate::get_custom_rendezvous_server\(get_option\("custom-rendezvous-server"\)\)\.is_empty\(\)',
    r"\1false",
    regex=True,
)
# Connect button: teal -> purple gradient pill (like the Drument login button)
patch(
    "flutter/lib/desktop/pages/connection_page.dart",
    r"child: ElevatedButton\(\s*onPressed: \(\) \{\s*onConnect\(\);\s*\},\s*child: Text\(translate\(\"Connect\"\)\),\s*\),",
    """child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                          colors: [Color(0xFF2FB393), Color(0xFF978EFB)]),
                      borderRadius: BorderRadius.circular(14.0),
                    ),
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        shadowColor: Colors.transparent,
                        foregroundColor: const Color(0xFF0B1220),
                      ),
                      onPressed: () {
                        onConnect();
                      },
                      child: Text(translate("Connect")),
                    ),
                  ),""".replace("\\","\\\\"),
    regex=True,
)
# Special look: soft navy -> teal glow behind the connect page
patch(
    "flutter/lib/desktop/pages/desktop_home_page.dart",
    r"return Container\(\s*color: Theme\.of\(context\)\.scaffoldBackgroundColor,\s*child: ConnectionPage\(\),\s*\);",
    """return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0B1220), Color(0xFF0E1D2B), Color(0xFF123232)],
        ),
      ),
      child: ConnectionPage(),
    );""".replace("\\","\\\\"),
    regex=True,
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
