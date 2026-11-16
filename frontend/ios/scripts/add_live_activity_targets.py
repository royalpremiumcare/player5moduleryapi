#!/usr/bin/env python3
"""Add the PlannWidgets widget-extension target and Live Activity sources to
frontend/ios/App/App.xcodeproj/project.pbxproj.

Idempotent: every object is added only if missing.  Extend FILES (one data
structure) to wire further source files (.swift or .m), then re-run --apply.

    python3 add_live_activity_targets.py --apply [path/to/project.pbxproj]
    python3 add_live_activity_targets.py --check [path/to/project.pbxproj]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IOS_DIR = os.path.normpath(os.path.join(HERE, ".."))
DEFAULT_PBX = os.path.join(IOS_DIR, "App", "App.xcodeproj", "project.pbxproj")
XCODEPROJ_DIR = os.path.join(IOS_DIR, "App")  # project dir = parent of the xcodeproj

PREFIX = "B2C3D4E5F6071829"  # + 8 hex digits; distinct from the spike's A1B2C3D4E5F60718...


def u(n):
    return f"{PREFIX}{n:08X}"


APP_TARGET = "504EC3031FED79650016851F"
PROJECT = "504EC2FC1FED79650016851F"
MAIN_GROUP = "504EC2FB1FED79650016851F"
PRODUCTS_GROUP = "504EC3051FED79650016851F"
APP_GROUP = "504EC3061FED79650016851F"
APP_SOURCES = "504EC3001FED79650016851F"
APP_DEBUG, APP_RELEASE = "504EC3171FED79650016851F", "504EC3181FED79650016851F"
CP_EMBED = "9592DBEFFC6D2A0C8D5DEB22"

EXT = "PlannWidgets"
EXT_BUNDLE_ID = "co.plannapp.app.widgets"
EXT_TARGET = u(0x01)
EXT_SOURCES, EXT_FRAMEWORKS, EXT_RESOURCES = u(0x02), u(0x03), u(0x04)
EMBED_PHASE = u(0x05)
PROXY, DEP = u(0x06), u(0x07)
EXT_CFG_LIST, EXT_DEBUG, EXT_RELEASE = u(0x08), u(0x09), u(0x0A)
APPEX_REF, APPEX_EMBED_BF = u(0x0B), u(0x0C)
EXT_PLIST_REF = u(0x0D)
GROUPS = {  # name -> (uid, path or None); None = existing/pathless handled below
    "Shared": (u(0x10), "Shared"),
    "LiveActivityCore": (u(0x11), None),
    EXT: (u(0x12), EXT),
}
EXISTING_GROUPS = {"App": APP_GROUP}

# One entry per source file (.swift or .m).  k = stable index (ref=u(0x100+4k), app bf +1, ext bf +2);
# never renumber existing entries.  path is relative to the xcodeproj directory
# (or to the group's own path when the group has one - then `path` is the basename).
CORE = "../LiveActivityCore/Sources/LiveActivityCore/"
FILES = [
    dict(k=0, name="PlannAppointmentAttributes.swift", path="PlannAppointmentAttributes.swift",
         group="Shared", disk="Shared/PlannAppointmentAttributes.swift", targets=("App", EXT)),
    dict(k=1, name="ContentModel.swift", path=CORE + "ContentModel.swift",
         group="LiveActivityCore", disk=CORE + "ContentModel.swift", targets=("App", EXT)),
    dict(k=2, name="LiveActivityAPI.swift", path=CORE + "LiveActivityAPI.swift",
         group="LiveActivityCore", disk=CORE + "LiveActivityAPI.swift", targets=("App",)),
    dict(k=3, name="ReconcileLogic.swift", path=CORE + "ReconcileLogic.swift",
         group="LiveActivityCore", disk=CORE + "ReconcileLogic.swift", targets=("App",)),
    dict(k=4, name="PlannWidgetsBundle.swift", path="PlannWidgetsBundle.swift",
         group=EXT, disk="PlannWidgets/PlannWidgetsBundle.swift", targets=(EXT,)),
    dict(k=5, name="AppointmentLiveActivity.swift", path="AppointmentLiveActivity.swift",
         group=EXT, disk="PlannWidgets/AppointmentLiveActivity.swift", targets=(EXT,)),
    dict(k=6, name="CoordinatorLogic.swift", path=CORE + "CoordinatorLogic.swift",
         group="LiveActivityCore", disk=CORE + "CoordinatorLogic.swift", targets=("App",)),
    dict(k=7, name="KeychainSecretStore.swift", path="KeychainSecretStore.swift",
         group="App", disk="App/KeychainSecretStore.swift", targets=("App",)),
    dict(k=8, name="URLSessionTransport.swift", path="URLSessionTransport.swift",
         group="App", disk="App/URLSessionTransport.swift", targets=("App",)),
    dict(k=9, name="LiveActivityCoordinator.swift", path="LiveActivityCoordinator.swift",
         group="App", disk="App/LiveActivityCoordinator.swift", targets=("App",)),
    dict(k=10, name="PlannLiveActivityPlugin.swift", path="PlannLiveActivityPlugin.swift",
         group="App", disk="App/PlannLiveActivityPlugin.swift", targets=("App",)),
    dict(k=11, name="PlannLiveActivityPlugin.m", path="PlannLiveActivityPlugin.m",
         group="App", disk="App/PlannLiveActivityPlugin.m", targets=("App",)),
]
FILE_TYPES = {".swift": "sourcecode.swift", ".m": "sourcecode.c.objc"}
for f in FILES:
    f["ftype"] = FILE_TYPES[os.path.splitext(f["name"])[1]]
    f["ref"] = u(0x100 + 4 * f["k"])
    f["bf"] = {"App": u(0x101 + 4 * f["k"]), EXT: u(0x102 + 4 * f["k"])}


def all_uids():
    ids = [EXT_TARGET, EXT_SOURCES, EXT_FRAMEWORKS, EXT_RESOURCES, EMBED_PHASE, PROXY, DEP,
           EXT_CFG_LIST, EXT_DEBUG, EXT_RELEASE, APPEX_REF, APPEX_EMBED_BF, EXT_PLIST_REF]
    ids += [g[0] for g in GROUPS.values()]
    for f in FILES:
        ids += [f["ref"], f["bf"]["App"], f["bf"][EXT]]
    return ids


# ---------------------------------------------------------------- text helpers
def block_span(src, uid):
    """Span of the multi-line object `uid` (from its header to its closing '};')."""
    m = re.search(r"^\t\t%s [^\n]*= \{\n" % uid, src, re.M)
    if not m:
        return None
    end = src.index("\n\t\t};\n", m.end()) + len("\n\t\t};\n")
    return m.start(), end


def list_items(src, uid, key):
    span = block_span(src, uid)
    if not span:
        return None
    blk = src[span[0]:span[1]]
    m = re.search(r"^\t\t\t%s = \(\n(.*?)^\t\t\t\);" % key, blk, re.M | re.S)
    if not m:
        return None
    return re.findall(r"^\t+([0-9A-F]{24}) ", m.group(1), re.M)


def add_to_list(src, uid, key, line, front=False, before_uid=None):
    span = block_span(src, uid)
    assert span, f"block {uid} not found"
    blk = src[span[0]:span[1]]
    m = re.search(r"^(\t\t\t%s = \(\n)(.*?)(^\t\t\t\);)" % key, blk, re.M | re.S)
    assert m, f"list {key} not found in {uid}"
    if before_uid:
        i = m.group(2).index(before_uid)
        i = m.group(2).rindex("\n", 0, i) + 1
        body = m.group(2)[:i] + line + m.group(2)[i:]
    elif front:
        body = line + m.group(2)
    else:
        body = m.group(2) + line
    blk = blk[:m.start(2)] + body + blk[m.end(2):]
    return src[:span[0]] + blk + src[span[1]:]


def insert_before(src, marker, text):
    assert src.count(marker) == 1, f"marker not unique: {marker!r}"
    return src.replace(marker, text + marker)


# ---------------------------------------------------------------- check
def check(path):
    errs = []
    src = open(path, encoding="utf-8").read()

    def need(cond, msg):
        if not cond:
            errs.append(msg)

    # uid collision: each of our uids must occur only as ours; non-ours must not use the prefix
    ids = all_uids()
    need(len(ids) == len(set(ids)), "generated UUIDs collide with each other")
    ours = set(ids)
    for found in set(re.findall(PREFIX + r"[0-9A-F]{8}", src)):
        need(found in ours, f"unknown UUID with our prefix in pbxproj: {found}")
    foreign = [m for m in set(re.findall(r"\b[0-9A-F]{24}\b", src)) if m in ours]
    need(True, "")  # (our ids are by construction prefix-only)

    # extension target
    span = block_span(src, EXT_TARGET)
    need(span, "target PlannWidgets missing")
    if span:
        blk = src[span[0]:span[1]]
        need("com.apple.product-type.app-extension" in blk, "target is not an app-extension")
        need(f"name = {EXT};" in blk, "target name")
    for cfg in (EXT_DEBUG, EXT_RELEASE):
        s = block_span(src, cfg)
        need(s, f"extension build config {cfg} missing")
        if s:
            b = src[s[0]:s[1]]
            for needle in (f"PRODUCT_BUNDLE_IDENTIFIER = {EXT_BUNDLE_ID};",
                           "IPHONEOS_DEPLOYMENT_TARGET = 16.2;", "CODE_SIGN_STYLE = Manual;",
                           "DEVELOPMENT_TEAM = 9V42VGDN9U;",
                           "INFOPLIST_FILE = PlannWidgets/Info.plist;",
                           "SKIP_INSTALL = YES;"):
                need(needle in b, f"{cfg}: missing {needle}")
    need(f"{EXT_TARGET} /* {EXT} */," in src.split("targets = (", 1)[-1].split(");", 1)[0],
         "target not in project targets list")
    need(f"{EXT_TARGET} = {{" in src, "TargetAttributes entry missing")

    # App target: phase order, dependency, LDFLAGS
    phases = list_items(src, APP_TARGET, "buildPhases") or []
    need(EMBED_PHASE in phases, "Embed Foundation Extensions not in App buildPhases")
    if EMBED_PHASE in phases and CP_EMBED in phases:
        need(phases.index(EMBED_PHASE) < phases.index(CP_EMBED),
             "Embed Foundation Extensions must come before [CP] Embed Pods Frameworks")
    need(DEP in (list_items(src, APP_TARGET, "dependencies") or []), "App missing target dependency")
    need(APPEX_EMBED_BF in (list_items(src, EMBED_PHASE, "files") or []), "appex not in embed phase")
    for cfg in (APP_DEBUG, APP_RELEASE):
        s = block_span(src, cfg)
        need(s and "-weak_framework ActivityKit" in src[s[0]:s[1]] and "$(inherited)" in
             re.search(r"OTHER_LDFLAGS = [^\n]*", src[s[0]:s[1]] or "").group(0)
             if s and "OTHER_LDFLAGS" in src[s[0]:s[1]] else False,
             f"App config {cfg}: OTHER_LDFLAGS must be inherited + -weak_framework ActivityKit")

    # files
    ext_src = list_items(src, EXT_SOURCES, "files") or []
    app_src = list_items(src, APP_SOURCES, "files") or []
    for f in FILES:
        need(re.search(r"%s /\* %s \*/ = \{isa = PBXFileReference; lastKnownFileType = %s; path = %s;" %
                       (f["ref"], re.escape(f["name"]), re.escape(f["ftype"]), re.escape(f["path"])), src),
             f"file ref missing: {f['name']}")
        need(os.path.exists(os.path.join(XCODEPROJ_DIR, f["disk"])),
             f"file not on disk: {f['disk']}")
        for tgt, lst in (("App", app_src), (EXT, ext_src)):
            want = tgt in f["targets"]
            need((f["bf"][tgt] in lst) == want,
                 f"{f['name']}: {'missing from' if want else 'must not be in'} {tgt} Sources")
            if want:
                need(re.search(r"%s /\* %s in Sources \*/ = \{isa = PBXBuildFile; fileRef = %s " %
                               (f["bf"][tgt], re.escape(f["name"]), f["ref"]), src),
                     f"{f['name']}: build file for {tgt} missing")
        gid = GROUPS[f["group"]][0] if f["group"] in GROUPS else EXISTING_GROUPS[f["group"]]
        need(f["ref"] in (list_items(src, gid, "children") or []), f"{f['name']}: not in group {f['group']}")
    need(EXT_PLIST_REF in (list_items(src, GROUPS[EXT][0], "children") or []), "ext Info.plist ref not in group")
    need(os.path.exists(os.path.join(XCODEPROJ_DIR, "PlannWidgets/Info.plist")), "PlannWidgets/Info.plist missing")
    return errs


# ---------------------------------------------------------------- apply
def apply(path):
    src = open(path, encoding="utf-8").read()
    has = lambda uid: re.search(r"^\t\t%s " % uid, src, re.M) is not None

    # ---- extension target (whole block applied at once)
    if not has(EXT_TARGET):
        src = insert_before(src, "/* End PBXBuildFile section */",
            f"\t\t{APPEX_EMBED_BF} /* {EXT}.appex in Embed Foundation Extensions */ = {{isa = PBXBuildFile; fileRef = {APPEX_REF} /* {EXT}.appex */; settings = {{ATTRIBUTES = (RemoveHeadersOnCopy, ); }}; }};\n")
        src = insert_before(src, "/* Begin PBXFileReference section */", (
            "/* Begin PBXContainerItemProxy section */\n"
            f"\t\t{PROXY} /* PBXContainerItemProxy */ = {{\n\t\t\tisa = PBXContainerItemProxy;\n"
            f"\t\t\tcontainerPortal = {PROJECT} /* Project object */;\n\t\t\tproxyType = 1;\n"
            f"\t\t\tremoteGlobalIDString = {EXT_TARGET};\n\t\t\tremoteInfo = {EXT};\n\t\t}};\n"
            "/* End PBXContainerItemProxy section */\n\n"
            "/* Begin PBXCopyFilesBuildPhase section */\n"
            f"\t\t{EMBED_PHASE} /* Embed Foundation Extensions */ = {{\n\t\t\tisa = PBXCopyFilesBuildPhase;\n"
            "\t\t\tbuildActionMask = 2147483647;\n\t\t\tdstPath = \"\";\n\t\t\tdstSubfolderSpec = 13;\n"
            f"\t\t\tfiles = (\n\t\t\t\t{APPEX_EMBED_BF} /* {EXT}.appex in Embed Foundation Extensions */,\n\t\t\t);\n"
            "\t\t\tname = \"Embed Foundation Extensions\";\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t};\n"
            "/* End PBXCopyFilesBuildPhase section */\n\n"))
        src = insert_before(src, "/* End PBXFileReference section */",
            f"\t\t{EXT_PLIST_REF} /* Info.plist */ = {{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = \"<group>\"; }};\n"
            f"\t\t{APPEX_REF} /* {EXT}.appex */ = {{isa = PBXFileReference; explicitFileType = \"wrapper.app-extension\"; includeInIndex = 0; path = {EXT}.appex; sourceTree = BUILT_PRODUCTS_DIR; }};\n")
        src = insert_before(src, "/* End PBXFrameworksBuildPhase section */",
            f"\t\t{EXT_FRAMEWORKS} /* Frameworks */ = {{\n\t\t\tisa = PBXFrameworksBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n"
            "\t\t\tfiles = (\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t};\n")
        src = add_to_list(src, PRODUCTS_GROUP, "children", f"\t\t\t\t{APPEX_REF} /* {EXT}.appex */,\n")
        src = add_to_list(src, APP_TARGET, "buildPhases",
                          f"\t\t\t\t{EMBED_PHASE} /* Embed Foundation Extensions */,\n", before_uid=CP_EMBED)
        src = add_to_list(src, APP_TARGET, "dependencies", f"\t\t\t\t{DEP} /* PBXTargetDependency */,\n")
        src = insert_before(src, "/* End PBXNativeTarget section */", (
            f"\t\t{EXT_TARGET} /* {EXT} */ = {{\n\t\t\tisa = PBXNativeTarget;\n"
            f"\t\t\tbuildConfigurationList = {EXT_CFG_LIST} /* Build configuration list for PBXNativeTarget \"{EXT}\" */;\n"
            f"\t\t\tbuildPhases = (\n\t\t\t\t{EXT_SOURCES} /* Sources */,\n\t\t\t\t{EXT_FRAMEWORKS} /* Frameworks */,\n\t\t\t\t{EXT_RESOURCES} /* Resources */,\n\t\t\t);\n"
            "\t\t\tbuildRules = (\n\t\t\t);\n\t\t\tdependencies = (\n\t\t\t);\n"
            f"\t\t\tname = {EXT};\n\t\t\tproductName = {EXT};\n\t\t\tproductReference = {APPEX_REF} /* {EXT}.appex */;\n"
            "\t\t\tproductType = \"com.apple.product-type.app-extension\";\n\t\t};\n"))
        attr_marker = "\t\t\t\t\t\tProvisioningStyle = Automatic;\n\t\t\t\t\t};\n"
        assert src.count(attr_marker) == 1
        src = src.replace(attr_marker, attr_marker +
            f"\t\t\t\t\t{EXT_TARGET} = {{\n\t\t\t\t\t\tCreatedOnToolsVersion = 26.0;\n\t\t\t\t\t\tProvisioningStyle = Manual;\n\t\t\t\t\t}};\n")
        src = add_to_list(src, PROJECT, "targets", f"\t\t\t\t{EXT_TARGET} /* {EXT} */,\n")
        src = insert_before(src, "/* End PBXResourcesBuildPhase section */",
            f"\t\t{EXT_RESOURCES} /* Resources */ = {{\n\t\t\tisa = PBXResourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n"
            "\t\t\tfiles = (\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t};\n")
        src = insert_before(src, "/* End PBXSourcesBuildPhase section */",
            f"\t\t{EXT_SOURCES} /* Sources */ = {{\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n"
            "\t\t\tfiles = (\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t};\n")
        src = insert_before(src, "/* Begin PBXVariantGroup section */", (
            "/* Begin PBXTargetDependency section */\n"
            f"\t\t{DEP} /* PBXTargetDependency */ = {{\n\t\t\tisa = PBXTargetDependency;\n"
            f"\t\t\ttarget = {EXT_TARGET} /* {EXT} */;\n\t\t\ttargetProxy = {PROXY} /* PBXContainerItemProxy */;\n\t\t}};\n"
            "/* End PBXTargetDependency section */\n\n"))

        def ext_cfg(uid, name, debug):
            cond = "DEBUG" if debug else '""'
            return (f"\t\t{uid} /* {name} */ = {{\n\t\t\tisa = XCBuildConfiguration;\n\t\t\tbuildSettings = {{\n"
                    "\t\t\t\tAPPLICATION_EXTENSION_API_ONLY = YES;\n\t\t\t\tCODE_SIGN_STYLE = Manual;\n"
                    "\t\t\t\tCURRENT_PROJECT_VERSION = 70;\n\t\t\t\tDEVELOPMENT_TEAM = 9V42VGDN9U;\n"
                    "\t\t\t\tGENERATE_INFOPLIST_FILE = NO;\n\t\t\t\tINFOPLIST_FILE = PlannWidgets/Info.plist;\n"
                    "\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 16.2;\n"
                    "\t\t\t\tLD_RUNPATH_SEARCH_PATHS = \"$(inherited) @executable_path/Frameworks @executable_path/../../Frameworks\";\n"
                    "\t\t\t\tMARKETING_VERSION = 6.4.2;\n"
                    f"\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {EXT_BUNDLE_ID};\n"
                    "\t\t\t\tPRODUCT_BUNDLE_PACKAGE_TYPE = \"XPC!\";\n\t\t\t\tPRODUCT_NAME = \"$(TARGET_NAME)\";\n"
                    "\t\t\t\tSKIP_INSTALL = YES;\n"
                    f"\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = {cond};\n"
                    "\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;\n\t\t\t\tSWIFT_VERSION = 5.0;\n"
                    "\t\t\t\tTARGETED_DEVICE_FAMILY = \"1,2\";\n\t\t\t};\n"
                    f"\t\t\tname = {name};\n\t\t}};\n")
        src = insert_before(src, "/* End XCBuildConfiguration section */",
                            ext_cfg(EXT_DEBUG, "Debug", True) + ext_cfg(EXT_RELEASE, "Release", False))
        src = insert_before(src, "/* End XCConfigurationList section */", (
            f"\t\t{EXT_CFG_LIST} /* Build configuration list for PBXNativeTarget \"{EXT}\" */ = {{\n"
            "\t\t\tisa = XCConfigurationList;\n\t\t\tbuildConfigurations = (\n"
            f"\t\t\t\t{EXT_DEBUG} /* Debug */,\n\t\t\t\t{EXT_RELEASE} /* Release */,\n\t\t\t);\n"
            "\t\t\tdefaultConfigurationIsVisible = 0;\n\t\t\tdefaultConfigurationName = Release;\n\t\t};\n"))
        # App: weak-link ActivityKit (app deploys to iOS 15; ActivityKit is iOS 16.1+)
        for cfg in (APP_DEBUG, APP_RELEASE):
            s = block_span(src, cfg)
            blk = src[s[0]:s[1]]
            if "OTHER_LDFLAGS" not in blk:
                anchor = "\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER"
                blk = blk.replace(anchor, "\t\t\t\tOTHER_LDFLAGS = \"$(inherited) -weak_framework ActivityKit\";\n" + anchor, 1)
                src = src[:s[0]] + blk + src[s[1]:]

    # ---- groups
    for name, (uid, gpath) in GROUPS.items():
        if has(uid):
            continue
        pathline = f"\t\t\tpath = {gpath};\n" if gpath else f"\t\t\tname = {name};\n"
        kids = ""
        if name == EXT:
            kids = f"\t\t\t\t{EXT_PLIST_REF} /* Info.plist */,\n"
        src = insert_before(src, "/* End PBXGroup section */",
            f"\t\t{uid} /* {name} */ = {{\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (\n{kids}\t\t\t);\n{pathline}\t\t\tsourceTree = \"<group>\";\n\t\t}};\n")
        src = add_to_list(src, MAIN_GROUP, "children", f"\t\t\t\t{uid} /* {name} */,\n")

    # ---- files
    for f in FILES:
        if has(f["ref"]) or f["ref"] + " /*" in src:
            continue
        src = insert_before(src, "/* End PBXFileReference section */",
            f"\t\t{f['ref']} /* {f['name']} */ = {{isa = PBXFileReference; lastKnownFileType = {f['ftype']}; path = {f['path']}; sourceTree = \"<group>\"; }};\n")
        bfs = ""
        for tgt in f["targets"]:
            bfs += f"\t\t{f['bf'][tgt]} /* {f['name']} in Sources */ = {{isa = PBXBuildFile; fileRef = {f['ref']} /* {f['name']} */; }};\n"
        src = insert_before(src, "/* End PBXBuildFile section */", bfs)
        gid = GROUPS[f["group"]][0] if f["group"] in GROUPS else EXISTING_GROUPS[f["group"]]
        src = add_to_list(src, gid, "children", f"\t\t\t\t{f['ref']} /* {f['name']} */,\n")
        for tgt in f["targets"]:
            phase = APP_SOURCES if tgt == "App" else EXT_SOURCES
            src = add_to_list(src, phase, "files", f"\t\t\t\t{f['bf'][tgt]} /* {f['name']} in Sources */,\n")

    open(path, "w", encoding="utf-8").write(src)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    path = args[0] if args else DEFAULT_PBX
    if flags == ["--check"]:
        errs = check(path)
        for e in errs:
            if e:
                print("FAIL:", e)
        print("CHECK", "OK" if not [e for e in errs if e] else "FAILED")
        sys.exit(1 if [e for e in errs if e] else 0)
    if flags == ["--apply"]:
        apply(path)
        print("applied")
        return
    sys.exit("usage: add_live_activity_targets.py (--apply|--check) [project.pbxproj]")


if __name__ == "__main__":
    main()
