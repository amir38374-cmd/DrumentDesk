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
                      gradient: LinearGradient(
                          colors: [MyTheme.accent, const Color(0xFF978EFB)]),
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
# ---- DruDesk full look: cards, menus, switches, toolbar
CARD = "BoxDecoration(color: const Color(0xFF111A2B), borderRadius: BorderRadius.circular(14.0), border: Border.all(color: const Color(0xFF1F2D47)))"
HOME = "flutter/lib/desktop/pages/desktop_home_page.dart"
# ID card
patch(HOME, r"margin: const EdgeInsets\.only\(left: 20, right: 11\),(\s*)height: 57,",
      r"margin: const EdgeInsets.only(left: 16, right: 12, top: 4),\1padding: const EdgeInsets.only(left: 10, right: 6),\1decoration: " + CARD + r",\1height: 62,", regex=True)
# password card
patch(HOME, r"margin: EdgeInsets\.only\(left: 20\.0, right: 16, top: 13, bottom: 13\),",
      "margin: const EdgeInsets.only(left: 16, right: 12, top: 8, bottom: 13),\n      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),\n      decoration: " + CARD + ",", regex=True)
# popup menus: rounded card
patch(COMMON, r"popupMenuTheme: PopupMenuThemeData\(\s*shape: RoundedRectangleBorder\(\s*side: BorderSide\(color: Colors\.white24\),\s*borderRadius: BorderRadius\.all\(Radius\.circular\(8\.0\)\),\s*\)\),",
      """popupMenuTheme: PopupMenuThemeData(
        color: const Color(0xFF111A2B),
        shape: RoundedRectangleBorder(
      side: const BorderSide(color: Color(0xFF1F2D47)),
      borderRadius: BorderRadius.all(Radius.circular(14.0)),
    )),""", regex=True)
# switches: teal when on
patch(COMMON, r"return SwitchThemeData\(\s*splashRadius: \(isDesktop \|\| isWebDesktop\) \? 0 : kRadialReactionRadius\);",
      """return SwitchThemeData(
        thumbColor: MaterialStateProperty.resolveWith((s) =>
            s.contains(MaterialState.selected) ? Colors.white : const Color(0xFF8A99B5)),
        trackColor: MaterialStateProperty.resolveWith((s) =>
            s.contains(MaterialState.selected) ? MyTheme.accent : const Color(0xFF243453)),
        splashRadius: (isDesktop || isWebDesktop) ? 0 : kRadialReactionRadius);""", regex=True)
# remote toolbar: pill shape
TB = "flutter/lib/desktop/widgets/remote_toolbar.dart"
patch(TB, "final toolbarBorderRadius = BorderRadius.all(Radius.circular(4.0));", "final toolbarBorderRadius = BorderRadius.all(Radius.circular(18.0));")
patch(TB, "static double menuBorderRadius = isWindows ? 5.0 : 7.0;", "static double menuBorderRadius = 14.0;")
patch(TB, "static const double menuButtonBorderRadius = 3.0;", "static const double menuButtonBorderRadius = 10.0;")
patch(TB, "static const double iconRadius = 8;", "static const double iconRadius = 12;")
# ---- DruDesk layout pass 2: flat cards, pill tabs, rounded input, pill status
patch(HOME, r"Container\(\s*width: 2,\s*decoration: const BoxDecoration\(color: MyTheme\.accent\),\s*\)\.marginOnly\(top: 5\),",
      "const SizedBox(width: 4),", regex=True)
patch(HOME, r"Container\(\s*width: 2,\s*height: 52,\s*decoration: BoxDecoration\(color: MyTheme\.accent\),?\s*\),",
      "const SizedBox(width: 4),", regex=True)
PT = "flutter/lib/common/widgets/peer_tab_page.dart"
patch(PT, r"final decoBorder = BoxDecoration\(\s*border: Border\(\s*bottom: BorderSide\(width: 2, color: color!\),\s*\)\);",
      "final decoBorder = BoxDecoration(color: const Color(0xFF133A3A), borderRadius: BorderRadius.circular(12.0));", regex=True)
patch(PT, r"borderRadius: BorderRadius\.circular\(6\)\);\s*final decoBorder", "borderRadius: BorderRadius.circular(12.0));\n          final decoBorder", regex=True)
patch(PT, r"child: Icon\(model\.tabIcon\(t\), color: color\)\s*\.paddingSymmetric\(horizontal: 4\),",
      "child: Icon(model.tabIcon(t), color: color)\n                            .paddingSymmetric(horizontal: 10, vertical: 7),", regex=True)
CP = "flutter/lib/desktop/pages/connection_page.dart"
patch(CP, r"Divider\(\)\.paddingOnly\(right: 12\),", "const SizedBox(height: 4),", regex=True)
patch(CP, r"if \(!isOutgoingOnly\) const Divider\(height: 1\),\s*if \(!isOutgoingOnly\) OnlineStatusWidget\(\)",
      """if (!isOutgoingOnly)
          Container(
            margin: const EdgeInsets.fromLTRB(12, 6, 12, 12),
            decoration: BoxDecoration(
              color: const Color(0xFF0F2A2A),
              borderRadius: BorderRadius.circular(16.0),
            ),
            child: OnlineStatusWidget(),
          )""", regex=True)
patch(CP, r"decoration: InputDecoration\(\s*filled: false,\s*counterText: '',",
      """decoration: InputDecoration(
                              filled: true,
                              fillColor: const Color(0xFF111A2B),
                              enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(14.0),
                                  borderSide: const BorderSide(color: Color(0xFF1F2D47), width: 1.5)),
                              focusedBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(14.0),
                                  borderSide: BorderSide(color: MyTheme.accent, width: 1.5)),
                              counterText: '',""", regex=True)
# ---- DruDesk tiles: ONE Settings tile + Recent/Favorites/... as square boxes under ID+password
TILES = """Widget buildTileGrid(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: gFFI.peerTabModel,
      child: Consumer<PeerTabModel>(builder: (context, model, child) {
        final tiles = <Widget>[
          ...model.visibleEnabledOrderedIndexs.map((t) => buildTile(
                context,
                PeerTabModel.icons[t],
                PeerTabModel.tabNames[t],
                model.currentTab == t,
                () async {
                  if (t != model.currentTab) {
                    model.setCurrentTabCachedPeers([]);
                  }
                  model.setCurrentTab(t);
                  if (t == 3) {
                    gFFI.abModel.pullAb(
                        force: ForcePullAb.listAndCurrent, quiet: false);
                  }
                  if (t == 4) {
                    gFFI.groupModel.pull(force: true);
                  }
                  await bind.setLocalFlutterOption(
                      k: kOptionPeerTabIndex, v: t.toString());
                },
              )),
          buildTile(context, Icons.settings_rounded, 'Settings', false,
              () => DesktopTabPage.onAddSetting()),
        ];
        return Container(
          margin: const EdgeInsets.fromLTRB(16, 0, 12, 12),
          child: GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 1.0,
            children: tiles,
          ),
        );
      }),
    );
  }

  Widget buildTile(BuildContext context, IconData icon, String label,
      bool selected, VoidCallback onTap) {
    return InkWell(
      borderRadius: BorderRadius.circular(14.0),
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: selected
              ? MyTheme.accent.withOpacity(0.18)
              : const Color(0xFF111A2B),
          borderRadius: BorderRadius.circular(14.0),
          border: Border.all(
              color: selected ? MyTheme.accent : const Color(0xFF1F2D47),
              width: selected ? 1.5 : 1.0),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: MyTheme.accent, size: 26),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Text(translate(label),
                  style: const TextStyle(fontSize: 11),
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis),
            ),
          ],
        ),
      ),
    );
  }

  Widget buildPopupMenu(BuildContext context) {"""
patch(HOME, "Widget buildPopupMenu(BuildContext context) {", TILES)
patch(HOME, "if (!isOutgoingOnly) buildPasswordBoard(context),",
      "if (!isOutgoingOnly) buildPasswordBoard(context),\n      if (!isOutgoingOnly) buildTileGrid(context),")
patch(HOME, "width: isIncomingOnly ? 280.0 : 200.0,", "width: 270.0,")
patch(HOME, "import 'package:flutter_hbb/models/platform_model.dart';",
      "import 'package:flutter_hbb/models/platform_model.dart';\nimport 'package:flutter_hbb/models/peer_tab_model.dart';\nimport 'package:flutter_hbb/models/ab_model.dart';")
# no second Settings: remove the dots button beside ID and the menu icon in the title bar
patch(HOME, "buildPopupMenu(context)", "const SizedBox.shrink()")
patch("flutter/lib/desktop/pages/desktop_tab_page.dart", "offstage: bind.isIncomingOnly() || bind.isDisableSettings(),", "offstage: true,")
# the old tab strip on the right is replaced by the tiles
patch("flutter/lib/common/widgets/peer_tab_page.dart",
      r"Expanded\(\s*child: visibleContextMenuListener\(\s*_createSwitchBar\(context\)\)\),",
      "const Expanded(child: SizedBox()),", regex=True)

# ---- accent color picker (saved, applies after restart)
patch(COMMON, "static const Color accent = Color(0xFF2FB393);",
"""static const Color accentDefault = Color(0xFF2FB393);
  static const List<int> accentChoices = [
    0xFF2FB393, 0xFFA5D86B, 0xFF978EFB, 0xFF5BA8F5, 0xFFF59E5B,
    0xFFF26B8A, 0xFFF5D04C, 0xFF4FD1C5, 0xFFE5534B, 0xFF7ED957,
    0xFFB084F5, 0xFF38BDF8, 0xFFFB7185, 0xFFFBBF24, 0xFF94A3B8,
  ];
  static Color loadAccent() {
    try {
      final v = bind.mainGetLocalOption(key: 'drudesk-accent');
      if (v.isNotEmpty) return Color(int.parse(v));
    } catch (_) {}
    return accentDefault;
  }
  static Color accent = loadAccent();""")
patch(COMMON, "static const Color accent50 = Color(0x772FB393);", "static Color accent50 = accent.withOpacity(0.47);")
patch(COMMON, "static const Color accent80 = Color(0xAA2FB393);", "static Color accent80 = accent.withOpacity(0.67);")
patch(COMMON, r"style: const TextStyle\(\s*color: MyTheme\.accent\)", "style: const TextStyle(color: MyTheme.accentDefault)", regex=True)
patch(COMMON, r"labelLarge: TextStyle\(fontSize: 16\.0, color: MyTheme\.accent80\)\)", "labelLarge: TextStyle(fontSize: 16.0, color: Color(0xAA2FB393)))", regex=True)
patch(COMMON, r"color: accent80,(\s*)\),(\s*)\),(\s*)cardColor: Color\(0xFF111A2B\)",
      r"color: Color(0xAA2FB393),\1),\2),\3cardColor: Color(0xFF111A2B)", regex=True)
patch("flutter/lib/desktop/pages/desktop_setting_page.dart", "const Color _accentColor = MyTheme.accent;", "const Color _accentColor = MyTheme.accentDefault;")
patch("flutter/lib/desktop/widgets/remote_toolbar.dart", "static const Color hoverBlueColor = MyTheme.accent;", "static const Color hoverBlueColor = MyTheme.accentDefault;")
patch("flutter/lib/desktop/widgets/popup_menu.dart", "static const Color commonColor = MyTheme.accent;", "static const Color commonColor = MyTheme.accentDefault;")
patch("flutter/lib/desktop/widgets/tabbar_widget.dart", "selectedTabIconColor: MyTheme.accent,", "selectedTabIconColor: MyTheme.accentDefault,", expected=2)
patch("flutter/lib/common/widgets/peer_tab_page.dart", "commonColor: MyTheme.accent,", "commonColor: MyTheme.accentDefault,")
SET = "flutter/lib/desktop/pages/desktop_setting_page.dart"
patch(SET, r"label: 'Follow System',(\s*)onChanged: isOptFixed \? null : onChanged\),(\s*)\]\);",
      r"label: 'Follow System',\1onChanged: isOptFixed ? null : onChanged),\2  _accentPicker(),\2]);", regex=True)
patch(SET, "Widget theme() {", """Widget _accentPicker() {
    final saved = bind.mainGetLocalOption(key: 'drudesk-accent');
    final sel = saved.isEmpty ? MyTheme.accentChoices.first.toString() : saved;
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(translate('Accent color')),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: MyTheme.accentChoices
                .map((c) => InkWell(
                      borderRadius: BorderRadius.circular(18.0),
                      onTap: () async {
                        await bind.mainSetLocalOption(
                            key: 'drudesk-accent', value: c.toString());
                        showToast(translate('Restart DruDesk to apply the color'));
                        setState(() {});
                      },
                      child: Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          color: Color(c),
                          shape: BoxShape.circle,
                          border: Border.all(
                              color: sel == c.toString()
                                  ? Colors.white
                                  : Colors.transparent,
                              width: 2.5),
                        ),
                      ),
                    ))
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget theme() {""")
# small visible strings
patch("src/platform/windows.rs", '"RustDesk Output"', f'"{APP} Output"')
patch("src/whiteboard/windows.rs", '"RustDesk whiteboard"', f'"{APP} whiteboard"')
patch("src/auth_2fa.rs", 'const ISSUER: &str = "RustDesk";', f'const ISSUER: &str = "{APP}";')

# ---- Android: own app id (so it installs next to the stock RustDesk), name, icon background
AND = "flutter/android/app/"
patch(AND + "build.gradle", 'applicationId "com.carriez.flutter_hbb"', 'applicationId "com.drument.drudesk"')
patch(AND + "src/main/AndroidManifest.xml", 'android:label="RustDesk"', 'android:label="' + APP + '"')
patch(AND + "src/main/AndroidManifest.xml", 'android:label="RustDesk Input"', 'android:label="' + APP + ' Input"')
patch(AND + "src/main/res/values/strings.xml", '<string name="app_name">RustDesk</string>', '<string name="app_name">' + APP + '</string>')
patch(AND + "src/main/res/values/ic_launcher_background.xml", "#ffffff", "#0B1220")
patch(AND + "src/main/kotlin/com/carriez/flutter_hbb/MainService.kt", 'const val DEFAULT_NOTIFY_TITLE = "RustDesk"', 'const val DEFAULT_NOTIFY_TITLE = "' + APP + '"')
patch(AND + "src/main/kotlin/com/carriez/flutter_hbb/BootReceiver.kt", '"RustDesk is Open"', '"' + APP + ' is Open"')

if errors:
    print("\nBRANDING FAILED:", file=sys.stderr)
    for e in errors:
        print("  -", e, file=sys.stderr)
    sys.exit(1)
print("\nBranding applied.")
