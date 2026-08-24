import json
import pytest

from backend.mobile_targets import detect_target, scaffold_for, verify_mobile_build
from backend.agent_pipeline import FrontendAgent, PipelineContext, PreviewAgent


def test_mobile_target_detection_defaults_native_requests_to_react_native(monkeypatch):
    monkeypatch.delenv("DEFAULT_MOBILE_TARGET", raising=False)
    assert detect_target("Build an iOS and Android mobile app") == "react-native"
    assert detect_target("Build this with Flutter") == "flutter"
    assert detect_target("Build a PWA") == "pwa"
    assert detect_target("Build a dashboard") == "web"


def test_react_native_scaffold_contains_release_contract():
    files = scaffold_for("react-native", "Field Ops")
    package = json.loads(files["mobile/package.json"])
    app = json.loads(files["mobile/app.json"])
    assert package["scripts"]["build:android"]
    assert package["scripts"]["build:ios"]
    assert app["expo"]["android"]["package"]
    assert app["expo"]["ios"]["bundleIdentifier"]
    assert "mobile/eas.json" in files
    assert "npm run typecheck" in files[".github/workflows/mobile-ci.yml"]


def test_flutter_scaffold_contains_analysis_tests_and_platform_bootstrap():
    files = scaffold_for("flutter", "Field Ops")
    assert "flutter_test" in files["mobile/pubspec.yaml"]
    assert "strict-casts" in files["mobile/analysis_options.yaml"]
    assert "flutter create --platforms android,ios" in files["mobile/README.md"]
    assert "flutter build appbundle --release" in files[".github/workflows/mobile-ci.yml"]


def test_pwa_scaffold_contains_install_and_offline_contract():
    files = scaffold_for("pwa", "Field Ops")
    manifest = json.loads(files["frontend/public/manifest.webmanifest"])
    assert manifest["display"] == "standalone"
    assert "fetch" in files["frontend/public/sw.js"]


def test_web_scaffold_is_a_complete_vite_tailwind_build_target():
    files = scaffold_for("web", "Field Ops")
    package = json.loads(files["frontend/package.json"])
    assert package["scripts"]["build"] == "tsc -b && vite build"
    assert "frontend/src/main.tsx" in files
    assert "frontend/tsconfig.json" in files
    assert "frontend/tailwind.config.js" in files
    assert "frontend/.env.example" in files
    assert "frontend/playwright.config.ts" in files
    assert "frontend/e2e/fullstack.spec.ts" in files
    assert package["scripts"]["e2e"] == "playwright test"


def test_missing_toolchain_is_reported_not_misrepresented(monkeypatch, tmp_path):
    (tmp_path / "mobile").mkdir()
    monkeypatch.setattr("backend.mobile_targets.shutil.which", lambda _name: None)
    result = verify_mobile_build(str(tmp_path), "flutter", enabled=True)
    assert result.status == "build_unverified_missing_toolchain"
    assert result.artifact is None


class MobileClient:
    async def chat_stream(self, messages, **_kwargs):
        request = messages[-1]["content"].lower()
        if "flutter presentation" in request:
            yield "import 'package:flutter/material.dart';\nclass GeneratedApp extends StatelessWidget { const GeneratedApp({super.key}); @override Widget build(BuildContext context) => MaterialApp(home: Scaffold(body: Semantics(label: 'Home', child: const Text('Ready')))); }\nvoid main()=>runApp(const GeneratedApp());"
        elif "expo router" in request:
            yield "import React from 'react';\nimport { SafeAreaView, Text } from 'react-native';\nexport default function Home(){return <SafeAreaView accessibilityLabel='Home'><Text>Ready</Text></SafeAreaView>}"
        else:
            yield "<!doctype html><html><head><style>body{background:linear-gradient(#07110d,#111);box-shadow:0 0 20px #000}@media(max-width:600px){body{padding:8px}}</style></head><body><button onclick=\"this.textContent='Ready'\">Run</button><button>Save</button><script>document.body.dataset.ready='true'</script></body></html>"


@pytest.mark.asyncio
@pytest.mark.parametrize(("target", "entry"), [("flutter", "mobile/lib/main.dart"), ("react-native", "mobile/app/index.tsx")])
async def test_active_frontend_agent_generates_mobile_project_contract(tmp_path, target, entry):
    context = PipelineContext(user_prompt="mobile", project_dir=str(tmp_path), target=target)
    context.set_artifact("PLAN.md", "# Mobile plan")
    context.set_artifact("design_tokens.json", json.dumps({"colors": {"primary": "#34d399"}, "typography": {"body": "Inter"}}))
    result = await FrontendAgent(MobileClient()).run(context)
    assert entry in result.artifacts
    assert "TARGET.json" in result.artifacts
    assert (tmp_path / entry).is_file()
    assert (tmp_path / ".github/workflows/mobile-ci.yml").is_file()


@pytest.mark.asyncio
async def test_preview_agent_materializes_offline_mobile_simulation(tmp_path):
    context = PipelineContext(user_prompt="mobile", project_dir=str(tmp_path), target="flutter")
    result = await PreviewAgent(MobileClient()).run(context)
    assert (tmp_path / "index.html").is_file()
    assert json.loads(result.artifacts["PREVIEW_MODE.json"])["mode"] == "mobile_simulation"
