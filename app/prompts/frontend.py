from langchain_core.prompts import PromptTemplate

frontend_prompt = PromptTemplate.from_template(
    """
You are an expert React frontend engineer generating a STRICT stack.
You must use explicitly: React, JavaScript, and Vite.
DO NOT use TypeScript (.ts or .tsx). Use .js and .jsx.
DO NOT use Create React App or react-scripts under any circumstances.

Given the API spec, generate all files:
You MUST follow the API contract shapes perfectly as specified. The components should use simple UI/Hooks.
IMPORTANT: You MUST ensure the API endpoint paths perfectly align with the backend spec (including trailing slashes).
Keep the UI incredibly simple (no advanced UI libraries like tailwind unless strictly requested). Simple buttons and inputs are completely fine.

Requirements for generated package.json at `frontend_root`:
- dependencies must include: react, react-dom
- devDependencies must include: vite, @vitejs/plugin-react
- scripts must include:
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"

Required files to explicitly generate along with source components:
- package.json
- vite.config.js (using defineConfig and @vitejs/plugin-react)
- index.html
- src/main.jsx
- src/App.jsx

Every local relative import in a generated source file MUST correspond to another generated file!
If you import `./index.css` or `./App.css`, you MUST generate them.

PORT AND PROXY CONVENTION:
- Vite MUST use port 5173 for the dev server.
- The Backend API is assumed to be running on port 3000.
- All API calls MUST use relative paths (e.g. `fetch('/api/notes')`). Do NOT hardcode `localhost:3000` or `localhost:5000` in your API calls.
- The backend natively exposes routes under `/api/...`, so the proxy must forward `/api/...` unchanged.
- You must generate EXACTLY this vite.config.js file (do NOT add a 'rewrite' property):

```javascript
import {{ defineConfig }} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({{
  plugins: [react()],
  server: {{
    port: 5173,
    proxy: {{
      '/api': {{
        target: 'http://localhost:3000',
        changeOrigin: true
      }}
    }}
  }}
}});
```

Specification:
{spec}
"""
)
