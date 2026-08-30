"""Structural checks on the iOS app bundle and its Xcode project.

These do not need Xcode: they verify that the generated offline bundle is in
step with its sources, that nothing in it reaches for the network, and that
every reference in project.pbxproj resolves to a file that exists.
"""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IOS_DIR = PROJECT_ROOT / "ios"
WWW_DIR = IOS_DIR / "MyConLearn" / "www"
PBXPROJ = IOS_DIR / "MyConLearn.xcodeproj" / "project.pbxproj"


def load_build_script():
    """Import scripts/build_ios_www.py, which is not part of a package."""
    spec = importlib.util.spec_from_file_location(
        "build_ios_www", PROJECT_ROOT / "scripts" / "build_ios_www.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pbxproj() -> dict:
    raw = subprocess.run(
        ["plutil", "-convert", "json", "-o", "-", str(PBXPROJ)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(raw)


class TestOfflineBundle:
    def test_bundle_is_up_to_date(self):
        """Rebuilding must be a no-op — otherwise the app ships stale vocab."""
        build = load_build_script()
        topics, cards = build.collect_vocab()

        assert (WWW_DIR / "vocab.js").read_text(encoding="utf-8") == build.render_vocab_js(
            topics, cards
        ), "vocab.js is stale — run: poetry run python scripts/build_ios_www.py"

        assert (WWW_DIR / "index.html").read_text(encoding="utf-8") == build.render_index_html(), (
            "index.html is stale — run: poetry run python scripts/build_ios_www.py"
        )

    def test_no_remote_assets(self):
        """Nothing may load over the network: the app has to work on a plane.

        Only attributes that actually fetch something count — SVG elements
        carry an xmlns URL that is an identifier, not a request.
        """
        html = (WWW_DIR / "index.html").read_text(encoding="utf-8")
        remote = re.findall(r"""(?:src|href)\s*=\s*["']https?:[^"']*""", html)
        remote += re.findall(r"""url\(\s*['"]?https?:[^)]*""", html)
        assert not remote, f"offline bundle still loads remote assets: {remote}"

    def test_required_files_present(self):
        for name in (
            "index.html",
            "vocab.js",
            "local-api.js",
            "mobile.css",
            "vendor/vue.global.prod.js",
            "vendor/tailwind.js",
        ):
            assert (WWW_DIR / name).is_file(), f"missing {name}"

    def test_offline_shim_loads_before_the_app(self):
        """local-api.js has to patch fetch before the Vue app calls it."""
        html = (WWW_DIR / "index.html").read_text(encoding="utf-8")
        assert html.index("local-api.js") < html.index("createApp")
        # vocab.js defines the data local-api.js reads at startup.
        assert html.index("vocab.js") < html.index("local-api.js")


class TestXcodeProject:
    def test_every_reference_resolves(self, pbxproj):
        objects = pbxproj["objects"]

        referenced = {pbxproj["rootObject"]}

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in {
                        "fileRef",
                        "productReference",
                        "buildConfigurationList",
                        "mainGroup",
                        "productRefGroup",
                    }:
                        referenced.add(value)
                    elif key in {
                        "children",
                        "files",
                        "buildConfigurations",
                        "targets",
                        "buildPhases",
                    }:
                        referenced.update(value)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(objects)

        assert not referenced - set(objects), "project.pbxproj references missing objects"
        assert not set(objects) - referenced, "project.pbxproj has orphaned objects"

    def test_file_references_exist_on_disk(self, pbxproj):
        objects = pbxproj["objects"]
        groups = {
            oid: obj for oid, obj in objects.items() if obj.get("isa") == "PBXGroup"
        }

        for oid, obj in objects.items():
            if obj.get("isa") != "PBXFileReference" or obj.get("sourceTree") != "<group>":
                continue

            owner = next(
                (group for group in groups.values() if oid in group.get("children", [])),
                None,
            )
            base = IOS_DIR / (owner.get("path", "") if owner else "")
            assert (base / obj["path"]).exists(), f"{obj['path']} is referenced but missing"

    def test_www_is_copied_as_a_folder(self, pbxproj):
        """A folder reference keeps new vocab files in the bundle automatically."""
        objects = pbxproj["objects"]
        www = next(
            obj
            for obj in objects.values()
            if obj.get("isa") == "PBXFileReference" and obj.get("path") == "www"
        )
        assert www["lastKnownFileType"] == "folder"

        resources = next(
            obj for obj in objects.values() if obj.get("isa") == "PBXResourcesBuildPhase"
        )
        copied = {objects[objects[bf]["fileRef"]]["path"] for bf in resources["files"]}
        assert "www" in copied
        assert "Assets.xcassets" in copied

    def test_bundle_identifier_is_consistent(self, pbxproj):
        """Progress lives in the app container, which is keyed by bundle id.

        Debug and Release must agree, or switching between them would look
        like the learner's history had been wiped.
        """
        objects = pbxproj["objects"]
        identifiers = {
            obj["buildSettings"]["PRODUCT_BUNDLE_IDENTIFIER"]
            for obj in objects.values()
            if obj.get("isa") == "XCBuildConfiguration"
            and "PRODUCT_BUNDLE_IDENTIFIER" in obj.get("buildSettings", {})
        }
        assert len(identifiers) == 1, f"bundle id differs between configurations: {identifiers}"

    def test_app_icon_is_opaque_and_square(self):
        """App Store icon slots reject alpha channels."""
        icon = (
            IOS_DIR
            / "MyConLearn"
            / "Assets.xcassets"
            / "AppIcon.appiconset"
            / "icon-1024.png"
        )
        header = icon.read_bytes()[:26]
        assert header[:8] == b"\x89PNG\r\n\x1a\n"

        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        colour_type = header[25]

        assert (width, height) == (1024, 1024)
        assert colour_type == 2, "icon must be RGB with no alpha channel"
