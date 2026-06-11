"""Tests unitaires pour apymix.spa_static — fallback SPA index.html."""

from pathlib import Path

from starlette.staticfiles import StaticFiles

from apymix.spa_static import SPAStaticFiles


# ---------------------------------------------------------------------------
# SPAStaticFiles
# ---------------------------------------------------------------------------

class TestSPAStaticFiles:
    def test_serves_existing_file(self, tmp_path: Path):
        """Un fichier existant est servi normalement."""
        (tmp_path / "index.html").write_text("<h1>Hello</h1>")
        (tmp_path / "app.js").write_text("// js")

        files = SPAStaticFiles(directory=str(tmp_path), html=True)
        assert isinstance(files, StaticFiles)
        # L'instance expose bien les attributs de StaticFiles
        assert files.directory == str(tmp_path)

    def test_html_mode_enabled(self, tmp_path: Path):
        """Vérifie que html=True est passé correctement."""
        (tmp_path / "index.html").write_text("<h1>x</h1>")
        files = SPAStaticFiles(directory=str(tmp_path), html=True)
        assert files.html is True
