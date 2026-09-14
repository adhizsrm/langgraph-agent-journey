import os
import shutil
import tempfile
import pytest
from app.tools.grep_tool import grep_search


class TestGrepDiscovery:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def write_file(self, path, content):
        full_path = os.path.join(self.test_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_react_style_project(self):
        self.write_file(
            "frontend/src/main.jsx",
            "import './index.css'; import App from './App'; ReactDOM.createRoot(document.getElementById('root')).render(<App />);",
        )
        self.write_file(
            "frontend/src/App.jsx",
            "export default function App() { return <div>dark mode is cool</div>; }",
        )
        self.write_file("frontend/src/index.css", "body { background: black; }")
        self.write_file("frontend/src/unrelated.jsx", "export const x = 1;")

        result = grep_search("Add dark mode", self.test_dir)
        # Should discover main.jsx via ReactDOM.createRoot, App.jsx via keyword "dark", index.css via import
        assert "frontend/src/main.jsx" in result
        assert "frontend/src/App.jsx" in result
        assert "frontend/src/index.css" in result
        # unrelated.jsx is not imported and does not have keyword, so should not be in result
        assert "frontend/src/unrelated.jsx" not in result

    def test_different_ts_structure(self):
        self.write_file(
            "src/bootstrap.tsx",
            "import { Root } from './Root'; import './styles/global.css'; ReactDOM.render(<Root />);",
        )
        self.write_file(
            "src/Root.tsx",
            "export const Root = () => <div>Implement dark mode here</div>;",
        )
        self.write_file("src/styles/global.css", "html { color: white; }")
        self.write_file("src/unrelated.ts", "const foo = 2;")

        result = grep_search("dark mode", self.test_dir)
        assert "src/bootstrap.tsx" in result
        assert "src/Root.tsx" in result
        assert "src/styles/global.css" in result
        assert "src/unrelated.ts" not in result

    def test_next_style_structure(self):
        self.write_file(
            "app/layout.tsx",
            "import './globals.css'; export default function RootLayout({ children }) { return <html><body>{children}</body></html>; }",
        )
        self.write_file(
            "app/page.tsx",
            "export default function Page() { return <div>We need dark mode</div>; }",
        )
        self.write_file("app/globals.css", "body { background: #fff; }")
        self.write_file("app/unrelated.tsx", "export const x = 1;")

        result = grep_search("dark mode", self.test_dir)
        assert "app/layout.tsx" in result
        assert "app/page.tsx" in result
        assert "app/globals.css" in result
        assert "app/unrelated.tsx" not in result

    def test_angular_vue_style(self):
        # Vue style
        self.write_file(
            "src/main.ts",
            "import { createApp } from 'vue'; import App from './App.vue'; import './style.css'; createApp(App).mount('#app');",
        )
        self.write_file("src/App.vue", "<template><div>Add dark mode</div></template>")
        self.write_file("src/style.css", "body {}")
        # I'll fake .vue by using .html since grep_tool searches js, jsx, ts, tsx, css, html, json, txt, md
        self.write_file("src/App.html", "<div>Add dark mode</div>")

        result = grep_search("dark mode", self.test_dir)
        assert "src/main.ts" in result
        assert "src/App.html" in result
        assert "src/style.css" in result

    def test_ignored_directories(self):
        self.write_file("node_modules/fake/main.jsx", "ReactDOM.createRoot()")
        self.write_file("dist/index.html", "<script src='main.js'></script>")
        self.write_file(".git/config", "bare = false")

        result = grep_search("dark mode", self.test_dir)
        assert len(result) == 0

    def test_keyword_match_is_not_automatically_entry_point(self):
        self.write_file("README.md", "This project has dark mode.")
        self.write_file("src/bootstrap.tsx", "ReactDOM.createRoot();")
        self.write_file("src/App.tsx", "const x = 1;")

        result = grep_search("dark mode", self.test_dir)
        # README.md is a keyword match. It should be in the result.
        # But it should NOT expand to everything unless it imports things.
        # bootstrap.tsx is an entry point. It's in the structural output and gets its imports expanded.
        assert "README.md" in result
        assert "src/bootstrap.tsx" in result

    def test_dark_mode_retrieval(self):
        self.write_file(
            "src/bootstrap.tsx",
            "import { RootView } from './RootView'; import './styles/global.css'; ReactDOM.createRoot();",
        )
        self.write_file(
            "src/RootView.tsx",
            "export const RootView = () => <div className='dark'>hello</div>;",
        )
        self.write_file("src/styles/global.css", ".dark { background: #000; }")
        # Notice we are searching for "Add dark mode", meaning "dark" and "mode" will match.
        result = grep_search("Add dark mode", self.test_dir)
        assert "src/bootstrap.tsx" in result
        assert "src/RootView.tsx" in result
        assert "src/styles/global.css" in result
