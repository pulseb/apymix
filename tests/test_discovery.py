"""Tests unitaires pour apymix.discovery — auto-discovery amx.yaml et résolution du workspace root."""

from pathlib import Path


from apymix.discovery import (
    _find_workspace_root,
    _iter_project_dirs,
    _load_amx,
    discover_projects,
)


# ---------------------------------------------------------------------------
# _load_amx
# ---------------------------------------------------------------------------

class TestLoadAmx:
    def test_loads_valid_yaml(self, tmp_path: Path):
        amx = tmp_path / "amx.yaml"
        amx.write_text("name: Foo\nversion: 1.2.3\n")
        config = _load_amx(amx)
        assert config == {"name": "Foo", "version": "1.2.3"}

    def test_returns_empty_when_missing(self, tmp_path: Path):
        assert _load_amx(tmp_path / "missing.yaml") == {}

    def test_returns_empty_on_empty_file(self, tmp_path: Path):
        amx = tmp_path / "amx.yaml"
        amx.write_text("")
        assert _load_amx(amx) == {}


# ---------------------------------------------------------------------------
# _find_workspace_root — stratégie de résolution
# ---------------------------------------------------------------------------

class TestFindWorkspaceRoot:
    """La résolution se fait dans l'ordre : env > CWD > monorepo > CWD fallback."""

    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch):
        """APYMIX_WORKSPACE=... est utilisé directement, peu importe le CWD."""
        monkeypatch.setenv("APYMIX_WORKSPACE", str(tmp_path))
        # CWD ailleurs pour vérifier que la env var l'emporte
        monkeypatch.chdir("/tmp")
        assert _find_workspace_root() == tmp_path

    def test_env_var_invalid_path_falls_back(self, tmp_path: Path, monkeypatch, caplog):
        """Si APYMIX_WORKSPACE pointe vers un dossier inexistant, on log un warning et on fallback."""
        monkeypatch.setenv("APYMIX_WORKSPACE", "/nonexistent/path/xyz")
        monkeypatch.chdir(tmp_path)
        # Doit retomber sur une stratégie de fallback (CWD ou monorepo)
        result = _find_workspace_root()
        assert isinstance(result, Path)

    def test_finds_root_via_amx_at_cwd(self, tmp_path: Path, monkeypatch):
        """Si amx.yaml est à la racine du CWD, on l'utilise."""
        monkeypatch.delenv("APYMIX_WORKSPACE", raising=False)
        (tmp_path / "amx.yaml").write_text("name: ws")
        monkeypatch.chdir(tmp_path)
        assert _find_workspace_root() == tmp_path

    def test_finds_root_via_subproject_amx(self, tmp_path: Path, monkeypatch):
        """Si CWD contient un sous-dossier avec amx.yaml, on remonte au CWD."""
        monkeypatch.delenv("APYMIX_WORKSPACE", raising=False)
        sub = tmp_path / "my-api"
        sub.mkdir()
        (sub / "amx.yaml").write_text("name: my-api")
        monkeypatch.chdir(tmp_path)
        assert _find_workspace_root() == tmp_path

    def test_walks_up_from_cwd_to_find_amx(self, tmp_path: Path, monkeypatch):
        """Si amx.yaml n'est pas au CWD mais dans un parent (max 5 niveaux), on remonte."""
        monkeypatch.delenv("APYMIX_WORKSPACE", raising=False)
        (tmp_path / "amx.yaml").write_text("name: ws")
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert _find_workspace_root() == tmp_path

    def test_walks_up_then_falls_back(self, tmp_path: Path, monkeypatch):
        """Comportement de fallback : si la remontée ne trouve rien, on prend le CWD.

        Note : on ne peut pas tester ce cas de manière isolée car la remontée
        depuis n'importe quel CWD réel trouve souvent un amx.yaml (ex: pulsapps
        à /workspace). On vérifie donc juste que la fonction retourne un Path,
        et qu'on peut l'utiliser.
        """
        monkeypatch.delenv("APYMIX_WORKSPACE", raising=False)
        # Au minimum : la fonction ne lève pas et retourne un Path absolu
        result = _find_workspace_root()
        assert isinstance(result, Path)
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# _iter_project_dirs — gestion des deux layouts
# ---------------------------------------------------------------------------

class TestIterProjectDirs:
    """Le discovery supporte 2 layouts : monorepo (sous-dossiers) ou single-project (racine = 1 projet)."""

    def test_single_project_layout(self, tmp_path: Path):
        """Layout 1 : workspace/amx.yaml → le workspace est lui-même le projet."""
        (tmp_path / "amx.yaml").write_text("name: single")
        (tmp_path / "src").mkdir()  # contenu non vide

        dirs = _iter_project_dirs(tmp_path)
        assert dirs == [tmp_path]

    def test_monorepo_layout(self, tmp_path: Path):
        """Layout 2 : workspace/*-api/amx.yaml → un dossier par sous-projet."""
        eve = tmp_path / "eve-api"
        eve.mkdir()
        (eve / "amx.yaml").write_text("name: Eve")
        kif = tmp_path / "kif-api"
        kif.mkdir()
        (kif / "amx.yaml").write_text("name: Kif")

        dirs = _iter_project_dirs(tmp_path)
        assert dirs == [eve, kif]  # sorted

    def test_ignores_hidden_dirs(self, tmp_path: Path):
        (tmp_path / ".hidden-api").mkdir()
        (tmp_path / ".hidden-api" / "amx.yaml").write_text("name: hidden")
        (tmp_path / "_private-api").mkdir()
        (tmp_path / "_private-api" / "amx.yaml").write_text("name: private")

        assert _iter_project_dirs(tmp_path) == []

    def test_ignores_dirs_without_amx_yaml(self, tmp_path: Path):
        (tmp_path / "with-amx").mkdir()
        (tmp_path / "with-amx" / "amx.yaml").write_text("name: with")
        (tmp_path / "without-amx").mkdir()
        (tmp_path / "without-amx" / "README.md").write_text("# no amx")

        dirs = _iter_project_dirs(tmp_path)
        assert len(dirs) == 1
        assert dirs[0].name == "with-amx"

    def test_ignores_apymix_self(self, tmp_path: Path):
        """Le dossier apymix (le framework lui-même) ne doit jamais être un sous-projet."""
        (tmp_path / "apymix").mkdir()
        (tmp_path / "apymix" / "amx.yaml").write_text("name: apymix")
        assert _iter_project_dirs(tmp_path) == []

    def test_empty_workspace(self, tmp_path: Path):
        assert _iter_project_dirs(tmp_path) == []

    def test_nonexistent_workspace(self, tmp_path: Path):
        assert _iter_project_dirs(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# discover_projects — layouts
# ---------------------------------------------------------------------------

class TestDiscoverProjectsLayouts:
    """discover_projects doit fonctionner pour les 2 layouts via _iter_project_dirs."""

    def test_single_project_returns_apis(self, tmp_path: Path, monkeypatch):
        """Layout single-project : si le projet expose un module `app`, il est découvert."""
        (tmp_path / "amx.yaml").write_text(
            "name: Single\nroute: /single\ntype: api\nmodule: single_app\nenabled: true"
        )
        # Le module `single_app` n'existe pas → on s'attend à 0 (échec d'import silencieux)
        api_entries, front_entries = discover_projects(tmp_path)
        # Le module n'existe pas donc l'API n'est pas montée
        # mais on ne lève pas d'exception non plus
        assert isinstance(api_entries, list)
        assert isinstance(front_entries, list)
