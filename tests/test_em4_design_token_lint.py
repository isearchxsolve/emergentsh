"""EM-4 regression tests: structural design-token lint.

Guards the audit gap: FrontendAgent's "architectural moat" was a string
search (`if "backdrop-blur" not in code and "transition" not in code`),
which any generated text containing those words passes and any legitimate
UI approach fails. The gate is now a structural lint: module structure,
component definition, >=N styling applications, motion/interaction
primitives, and fidelity to the designer's palette.
"""
import json

from backend.agent_pipeline import (
    extract_palette_colors,
    lint_frontend_design_tokens,
)

DESIGN = {
    "colors": {
        "primary": "#0ea5e9",
        "background": "#0f172a",
        "text": "#f8fafc",
    },
    "typography": {"font": "Inter"},
}

COMPLIANT = """import React from 'react';
import './App.css';

export default function Dashboard() {
  return (
    <main className="bg-[#0f172a] text-[#f8fafc] min-h-screen">
      <header className="border-b border-[#0ea5e9]/30 transition-colors">
        <h1 className="text-2xl font-bold text-[#0ea5e9]">Task Manager</h1>
      </header>
      <section className="grid gap-4 p-6">
        <div className="rounded-xl bg-[#1e293b] p-4 hover:scale-[1.02] transition-transform">
          <p>Project card</p>
        </div>
      </section>
    </main>
  );
}
"""


class TestLintCompliance:
    def test_compliant_page_passes(self):
        assert lint_frontend_design_tokens(COMPLIANT, DESIGN) == []

    def test_compliant_page_without_design_still_passes(self):
        assert lint_frontend_design_tokens(COMPLIANT, None) == []

    def test_empty_code_fails(self):
        violations = lint_frontend_design_tokens("", DESIGN)
        assert violations, "empty code must fail the gate"

    def test_plain_text_fails(self):
        violations = lint_frontend_design_tokens("just some words, no code", DESIGN)
        assert any("module structure" in v for v in violations)


class TestLintViolationCategories:
    def test_no_component_definition(self):
        code = "import x from 'y';\nconst data = { a: 1 };\nexport default data;\n"
        violations = lint_frontend_design_tokens(code, None)
        assert any("component definition" in v for v in violations)

    def test_too_few_style_applications(self):
        code = (
            "import React from 'react';\n"
            "export default function App() {\n"
            "  return <div className='text-[#0ea5e9] transition'>hi</div>;\n"
            "}\n"
        )
        violations = lint_frontend_design_tokens(code, DESIGN)
        assert any("styling application" in v for v in violations)

    def test_no_motion_primitives(self):
        code = (
            "import React from 'react';\n"
            "export default function App() {\n"
            "  return (\n"
            "    <div className='a' style={{color: '#0ea5e9'}}>\n"
            "      <p className='b'>x</p>\n"
            "      <span className='c'>y</span>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        violations = lint_frontend_design_tokens(code, DESIGN)
        assert any("motion" in v for v in violations)

    def test_palette_fidelity_failure(self):
        """Structurally fine code that ignores the designer's palette fails."""
        code = (
            "import React from 'react';\n"
            "export default function App() {\n"
            "  return (\n"
            "    <div className='bg-red-500 transition'>\n"
            "      <p style={{color: 'hotpink'}}>x</p>\n"
            "      <span className='text-green-200'>y</span>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        violations = lint_frontend_design_tokens(code, DESIGN)
        assert any("palette fidelity" in v for v in violations)

    def test_palette_fidelity_pass_when_color_present(self):
        code = (
            "import React from 'react';\n"
            "export default function App() {\n"
            "  return (\n"
            "    <div className='bg-[#0ea5e9] transition'>\n"
            "      <p className='a'>x</p>\n"
            "      <span className='b'>y</span>\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )
        assert lint_frontend_design_tokens(code, DESIGN) == []


class TestPaletteExtraction:
    def test_dict_colors_section(self):
        assert extract_palette_colors(DESIGN) == ["#0ea5e9", "#0f172a", "#f8fafc"]

    def test_list_colors_section(self):
        assert extract_palette_colors({"colors": ["#aabbcc", "nope", "#112233"]}) == [
            "#aabbcc",
            "#112233",
        ]

    def test_missing_colors_section(self):
        assert extract_palette_colors({"typography": {}}) == []

    def test_color_palette_alias(self):
        assert extract_palette_colors({"color_palette": {"a": "#abcdef"}}) == ["#abcdef"]


class TestFrontendAgentUsesLint:
    """The agent must route through the structural lint, not a string search."""

    def test_no_backdrop_blur_string_search_remains(self):
        import inspect

        from backend.agent_pipeline import FrontendAgent

        source = inspect.getsource(FrontendAgent.run)
        assert '"backdrop-blur" not in code' not in source, (
            "the old string-search gate must be gone"
        )
        assert "lint_frontend_design_tokens" in source
