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
        # Undirected Next.js structures (layout not directly importing page)
        # result in page isolated. layout.tsx discarded since it lacks a path to the match.
        assert "app/page.tsx" in result
        assert "app/layout.tsx" not in result

    def test_angular_vue_style(self):
        # Vue style
        self.write_file(
            "src/main.ts",
            "import { createApp } from 'vue'; import App from './App.vue'; import './style.css'; createApp(App).mount('#app');",
        )
        self.write_file(
            "src/App.vue", "<template><div>Add dark mode</div></template>"
        )
        self.write_file("src/style.css", "body {}")
        # We'll fake .vue by using .html since grep_tool searches it
        self.write_file("src/DarkMode.html", "<div>Add dark mode</div>")

        result = grep_search("dark mode", self.test_dir)

        # main.ts was faked to import './App.vue', but the file is 'DarkMode.html'.
        # Since extract_local_imports doesn't transparently map .vue to .html in its resolution array,
        # the import edge breaks.
        # Thus main.ts is discarded because it has no unbroken path to the match!
        # DarkMode.html is retained as an orphan because its filename matches the search intent.
        assert "src/DarkMode.html" in result
        assert "src/main.ts" not in result

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
        # README.md is a keyword match. It should be in the result as an orphan.
        assert "README.md" in result

        # bootstrap.tsx is an entry point. But it has no path to the keyword match.
        # Under Lineage Pathing, it is correctly discarded entirely.
        assert "src/bootstrap.tsx" not in result

    def test_dark_mode_retrieval(self):
        # Frontend Entry
        self.write_file(
            "frontend/src/bootstrap.tsx",
            "import { RootView } from './RootView'; import './styles/global.css'; ReactDOM.createRoot();",
        )
        self.write_file(
            "frontend/src/RootView.tsx",
            "import { UnrelatedSibling } from './UnrelatedSibling'; export const RootView = () => <div className='dark'>Add dark mode</div>;",
        )
        self.write_file("frontend/src/styles/global.css", ".dark { background: #000; }")
        self.write_file(
            "frontend/src/UnrelatedSibling.tsx",
            "export const UnrelatedSibling = () => <div/>;",
        )

        # Backend Entry
        self.write_file(
            "backend/src/index.js", "import './routes.js'; app.listen(3000);"
        )
        self.write_file("backend/src/routes.js", "console.log('routes');")

        result = grep_search("Add dark mode", self.test_dir)

        # Entry shell is included + lineage Match
        assert "frontend/src/bootstrap.tsx" in result
        assert "frontend/src/RootView.tsx" in result

        # Styling of lineage is included
        assert "frontend/src/styles/global.css" in result

        # Non-entry sibling is perfectly excluded (RootView.tsx is not an entry point, so it does not horizontally expand)
        assert "frontend/src/UnrelatedSibling.tsx" not in result

        # Backend tree is fully excluded (No lineage path to the keyword match)
        assert "backend/src/index.js" not in result
        assert "backend/src/routes.js" not in result

    def test_lineage_preserves_nested_nested_match(self):
        # Lineage from entry point to a nested relevant component is preserved without horizontal bloat
        self.write_file(
            "src/main.jsx", "import App from './App.jsx'; ReactDOM.createRoot();"
        )
        self.write_file(
            "src/App.jsx",
            "import NoteList from './NoteList.jsx'; import NoteForm from './NoteForm.jsx';",
        )
        self.write_file(
            "src/NoteList.jsx",
            "import NoteListCSS from './NoteList.css'; // Notes search bar feature",
        )
        self.write_file("src/NoteList.css", ".note-list { }")
        self.write_file("src/NoteForm.jsx", "// Unrelated form")

        result = grep_search("Notes search bar", self.test_dir)

        # Ensure path from root to NoteList is fully captured
        assert "src/main.jsx" in result
        assert "src/App.jsx" in result
        assert "src/NoteList.jsx" in result

        # Styling attached to lineage is captured
        assert "src/NoteList.css" in result

        # Unrelated sibling (NoteForm) imported by App.jsx is explicitly discarded
        assert "src/NoteForm.jsx" not in result

    def test_stop_words_are_ignored(self):
        # Provide entry point to ensure it's not pruned as a noise orphan
        self.write_file(
            "frontend/src/main.tsx", "import './App'; ReactDOM.createRoot();"
        )
        self.write_file("backend/routes/auth.ts", "Here is a file that handles auth.")
        self.write_file(
            "README.md", "This document explains things with some generic words."
        )
        self.write_file(
            "frontend/src/App.tsx", "Here is the search feature with categories."
        )

        result = grep_search(
            "Add a search bar that filters by categories", self.test_dir
        )

        # Stop words like 'that', 'add' are ignored
        assert "backend/routes/auth.ts" not in result
        assert "README.md" not in result

        # Meaningful features are retrieved
        assert "frontend/src/App.tsx" in result

    def test_orphan_relevance_policy(self):
        # 1. Real application files in the dependency graph
        self.write_file(
            "frontend/src/main.tsx", "import './App'; ReactDOM.createRoot();"
        )
        self.write_file(
            "frontend/src/App.tsx",
            "import { FilterPanel } from './components/FilterPanel';",
        )
        self.write_file(
            "frontend/src/components/FilterPanel.tsx",
            "Search bar that filters expenses by category",
        )
        self.write_file(
            "backend/src/server.ts", "import './routes/expenses'; app.listen(3000);"
        )
        self.write_file(
            "backend/src/routes/expenses.ts", "router.get('/expenses', ...)"
        )

        # 2. Unrelated noise files containing generic keywords but not in dependency graph (Orphans without intent)
        self.write_file("backend/test_security.js", "tests expense security")
        self.write_file("backend/test_jwt.js", "tests expense jwt filtering")
        self.write_file("backend/check_schema.js", "checks categories")
        self.write_file("gitlog.js", "commit add search bar")

        # 3. Orphan matching filename-keyword intent
        self.write_file("scripts/seed_expenses.js", "seed expenses data")

        # 4. Orphan matching configuration document
        self.write_file("vite.config.ts", "category config expenses")

        result = grep_search(
            "Add a search bar that filters expenses by category", self.test_dir
        )

        # Connected app files retained
        assert "frontend/src/main.tsx" in result
        assert "frontend/src/App.tsx" in result
        assert "frontend/src/components/FilterPanel.tsx" in result
        assert "backend/src/server.ts" in result
        assert "backend/src/routes/expenses.ts" in result

        # Unrelated diagnostic/test files excluded (content keyword matches failed the orphan structural role test)
        assert "backend/test_security.js" not in result
        assert "backend/test_jwt.js" not in result
        assert "backend/check_schema.js" not in result
        assert "gitlog.js" not in result

        # Filename intent match retained
        assert "scripts/seed_expenses.js" in result

        # Configuration match retained
        assert "vite.config.ts" in result
