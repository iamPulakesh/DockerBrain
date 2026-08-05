from __future__ import annotations
import importlib.resources

TEMPLATES_META: dict[str, dict[str, str]] = {
    "fastapi": {"name": "FastAPI", "description": "Python FastAPI with uvicorn"},
    "flask": {"name": "Flask", "description": "Python Flask with gunicorn"},
    "django": {"name": "Django", "description": "Python Django with gunicorn"},
    "python": {"name": "Python", "description": "Generic Python script or app"},
    "php": {"name": "PHP", "description": "Generic PHP with Apache"},
    "cpp": {"name": "C++", "description": "C++ with CMake build"},
    "swift": {"name": "Swift", "description": "Swift / Vapor backend"},
    "ktor": {"name": "Kotlin / Ktor", "description": "Kotlin Ktor with Gradle"},
    "node": {"name": "Node.js", "description": "Node.js (Express / generic)"},
    "nextjs": {"name": "Next.js", "description": "Next.js with standalone output"},
    "react": {"name": "React", "description": "React (Vite/CRA) with nginx"},
    "vue": {"name": "Vue.js", "description": "Vue.js with nginx"},
    "angular": {"name": "Angular", "description": "Angular with nginx"},
    "bun": {"name": "Bun", "description": "Bun runtime"},
    "deno": {"name": "Deno", "description": "Deno runtime"},
    "go": {"name": "Go", "description": "Go with multi-stage build"},
    "rust": {"name": "Rust", "description": "Rust with multi-stage build"},
    "spring": {"name": "Spring Boot", "description": "Spring Boot (Maven)"},
    "gradle": {"name": "Java (Gradle)", "description": "Java app with Gradle"},
    "rails": {"name": "Ruby on Rails", "description": "Rails with Puma"},
    "laravel": {"name": "Laravel", "description": "PHP Laravel with Apache"},
    "dotnet": {"name": ".NET", "description": "ASP.NET Core"},
    "phoenix": {"name": "Elixir Phoenix", "description": "Phoenix Framework"},
    "static": {"name": "Static Site", "description": "Static HTML/CSS/JS with nginx"},
    "python-ml": {"name": "Python ML", "description": "Python ML/Data Science with Jupyter"},
    "sveltekit": {"name": "SvelteKit", "description": "SvelteKit with Node adapter"},
    "nuxtjs": {"name": "Nuxt.js", "description": "Nuxt.js with SSR output"},
    "astro": {"name": "Astro", "description": "Astro static site with nginx"},
    "streamlit": {"name": "Streamlit", "description": "Python Streamlit data app"},
    "nestjs": {"name": "NestJS", "description": "NestJS backend with multi-stage build"},
}

def get_template_names() -> list[str]:
    """Return sorted list of template keys."""
    return sorted(TEMPLATES_META.keys())

def get_template(name: str) -> dict[str, str] | None:
    """Return template dict by key, or None."""
    key = name.lower()
    meta = TEMPLATES_META.get(key)
    if not meta:
        return None
    
    try:
        content = importlib.resources.files("dockerbrain.templates.data").joinpath(f"{key}.Dockerfile").read_text(encoding="utf-8")
    except Exception:
        content = ""
        
    return {
        "name": meta["name"],
        "description": meta["description"],
        "dockerfile": content
    }
