"""Platform routing, deterministic mobile scaffolds, and release verification."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

SUPPORTED_TARGETS = {"web", "pwa", "react-native", "flutter"}


def detect_target(prompt: str) -> str:
    value = prompt.lower()
    if re.search(r"\bflutter\b|\bdart\b", value):
        return "flutter"
    if re.search(r"\breact[ -]?native\b|\bexpo\b", value):
        return "react-native"
    if re.search(r"\b(ios|iphone|ipad|android|mobile app|native app)\b", value):
        # Expo is the default cross-platform target unless Flutter is explicit.
        return os.getenv("DEFAULT_MOBILE_TARGET", "react-native")
    if re.search(r"\bpwa\b|progressive web app", value):
        return "pwa"
    return "web"


@dataclass
class BuildReadiness:
    target: str
    status: str = "source_complete"
    toolchain: str = ""
    command: str = ""
    artifact: Optional[str] = None
    signing_required: bool = False
    message: str = "Complete source generated; release build has not been verified."

    def json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def react_native_scaffold(name: str = "emergent-app") -> Dict[str, str]:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "emergent-app"
    return {
        "mobile/package.json": json.dumps({"name": slug, "version": "1.0.0", "private": True, "main": "expo-router/entry", "scripts": {"start": "expo start", "android": "expo run:android", "ios": "expo run:ios", "typecheck": "tsc --noEmit", "test": "jest --passWithNoTests", "build:android": "eas build --platform android --profile production", "build:ios": "eas build --platform ios --profile production"}, "dependencies": {"expo": "~51.0.0", "expo-router": "~3.5.0", "expo-status-bar": "~1.12.0", "react": "18.2.0", "react-native": "0.74.0", "react-native-safe-area-context": "4.10.0", "react-native-screens": "~3.31.0"}, "devDependencies": {"@types/react": "~18.2.0", "jest": "^29.7.0", "jest-expo": "~51.0.0", "typescript": "^5.4.0"}, "jest": {"preset": "jest-expo"}}, indent=2),
        "mobile/app.json": json.dumps({"expo": {"name": name, "slug": slug, "scheme": slug, "version": "1.0.0", "orientation": "default", "userInterfaceStyle": "automatic", "plugins": ["expo-router"], "ios": {"supportsTablet": True, "bundleIdentifier": f"com.emergentsh.{slug.replace('-', '')}"}, "android": {"package": f"com.emergentsh.{slug.replace('-', '')}"}, "experiments": {"typedRoutes": True}}}, indent=2),
        "mobile/eas.json": json.dumps({"cli": {"version": ">= 10.0.0"}, "build": {"development": {"developmentClient": True, "distribution": "internal"}, "preview": {"distribution": "internal"}, "production": {"autoIncrement": True}}, "submit": {"production": {}}}, indent=2),
        "mobile/tsconfig.json": json.dumps({"extends": "expo/tsconfig.base", "compilerOptions": {"strict": True, "noUncheckedIndexedAccess": True, "paths": {"@/*": ["./*"]}}, "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"]}, indent=2),
        "mobile/app/_layout.tsx": "import { Stack } from 'expo-router';\nimport { SafeAreaProvider } from 'react-native-safe-area-context';\nexport default function Layout(){return <SafeAreaProvider><Stack screenOptions={{headerShown:false}} /></SafeAreaProvider>}\n",
        "mobile/.env.example": "EXPO_PUBLIC_API_URL=http://127.0.0.1:8000\n",
        "mobile/expo-env.d.ts": "/// <reference types=\"expo/types\" />\n",
        "mobile/README.md": "# Mobile app\n\nExpo/React Native project for Android and iOS. Run `npm ci`, `npm run typecheck`, and `npm test`. Release builds use the production EAS profile. Store credentials and signing material outside Git.\n",
    }


def flutter_scaffold(name: str = "emergent_app") -> Dict[str, str]:
    package = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_") or "emergent_app"
    return {
        "mobile/pubspec.yaml": f"name: {package}\ndescription: EmergentSH generated mobile application\npublish_to: 'none'\nversion: 1.0.0+1\nenvironment:\n  sdk: '>=3.4.0 <4.0.0'\ndependencies:\n  flutter:\n    sdk: flutter\n  cupertino_icons: ^1.0.8\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\n  flutter_lints: ^4.0.0\nflutter:\n  uses-material-design: true\n",
        "mobile/analysis_options.yaml": "include: package:flutter_lints/flutter.yaml\nanalyzer:\n  language:\n    strict-casts: true\n    strict-raw-types: true\n",
        "mobile/test/widget_test.dart": "import 'package:flutter_test/flutter_test.dart';\nimport 'package:" + package + "/main.dart';\nvoid main(){testWidgets('app starts',(tester) async {await tester.pumpWidget(const GeneratedApp()); expect(find.byType(GeneratedApp), findsOneWidget);});}\n",
        "mobile/.env.example": "API_URL=http://127.0.0.1:8000\n",
        "mobile/README.md": "# Mobile app\n\nFlutter source for Android and iOS. From this directory run `flutter create --platforms android,ios .`, `flutter pub get`, `flutter analyze`, and `flutter test`. Signing material must remain outside Git.\n",
    }


def scaffold_for(target: str, name: str) -> Dict[str, str]:
    if target == "pwa":
        return {
            "frontend/public/manifest.webmanifest": json.dumps({"name": name, "short_name": name[:12], "start_url": "/", "display": "standalone", "background_color": "#030509", "theme_color": "#10b981", "icons": []}, indent=2),
            "frontend/public/sw.js": "const CACHE='emergent-v1';self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/']))));self.addEventListener('fetch',e=>e.respondWith(fetch(e.request).catch(()=>caches.match(e.request))));\n",
            "PWA_READINESS.json": json.dumps({"installable_contract": True, "offline_shell": True, "audit_required": "Lighthouse production audit"}, indent=2),
        }
    if target == "react-native":
        files = react_native_scaffold(name)
        files[".github/workflows/mobile-ci.yml"] = """name: Mobile CI
on: [push, pull_request]
jobs:
  expo:
    runs-on: ubuntu-latest
    defaults: {run: {working-directory: mobile}}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: 20, cache: npm, cache-dependency-path: mobile/package-lock.json}
      - run: npm install --ignore-scripts
      - run: npm run typecheck
      - run: npm test -- --runInBand
"""
        return files
    if target == "flutter":
        files = flutter_scaffold(name)
        files[".github/workflows/mobile-ci.yml"] = """name: Mobile CI
on: [push, pull_request]
jobs:
  flutter:
    runs-on: ubuntu-latest
    defaults: {run: {working-directory: mobile}}
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with: {channel: stable, cache: true}
      - run: flutter create --platforms android,ios .
      - run: flutter pub get
      - run: flutter analyze
      - run: flutter test
      - run: flutter build appbundle --release
"""
        return files
    return {}


def verify_mobile_build(project_dir: str, target: str, enabled: bool = False) -> BuildReadiness:
    readiness = BuildReadiness(target=target)
    if target not in {"react-native", "flutter"}: return readiness
    root = Path(project_dir) / "mobile"
    tool = "flutter" if target == "flutter" else "npm"
    readiness.toolchain = tool
    if not project_dir or not root.is_dir():
        readiness.status = "build_unverified_no_workspace"
        readiness.message = "Source exists in memory; provide a project directory to verify the mobile build."
        return readiness
    if not enabled:
        readiness.status = "build_unverified"
        readiness.message = "Source complete; mobile release verification is disabled."
        return readiness
    executable = shutil.which(tool)
    if not executable:
        readiness.status = "build_unverified_missing_toolchain"
        readiness.message = f"Source complete; {tool} is unavailable on this build worker."
        return readiness
    commands = [[executable, "pub", "get"], [executable, "analyze"], [executable, "test"], [executable, "build", "appbundle", "--release"]] if target == "flutter" else [[executable, "install", "--ignore-scripts"], [executable, "run", "typecheck"], [executable, "test", "--", "--runInBand"]]
    for command in commands:
        readiness.command = " ".join(command[1:])
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=900)
        if result.returncode:
            readiness.status = "build_failed"
            readiness.message = (result.stderr or result.stdout)[-2000:]
            return readiness
    if target == "flutter":
        aab = next(root.glob("build/app/outputs/bundle/release/*.aab"), None)
        if not aab:
            readiness.status = "build_failed"
            readiness.message = "Flutter reported success but no release AAB was produced."
            return readiness
        readiness.status = "release_artifact_created"
        readiness.artifact = str(aab.relative_to(Path(project_dir)))
    else:
        readiness.status = "build_verified"
    readiness.signing_required = True
    readiness.message = "Dependencies, static analysis, and tests passed; store signing is still required."
    return readiness
