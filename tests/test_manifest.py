"""Tests unitaires pour apymix.manifest — parsing amx.yaml et helpers."""

import textwrap
from pathlib import Path


from apymix.manifest import AmxConfig, load_amx_config, make_tablename


# ---------------------------------------------------------------------------
# make_tablename
# ---------------------------------------------------------------------------

class TestMakeTablename:
    """Tests pour la fonction utilitaire de construction de noms de table."""

    def test_simple_prefix(self):
        assert make_tablename("eve_", "events") == "eve_events"

    def test_empty_prefix(self):
        assert make_tablename("", "events") == "events"

    def test_prefix_without_underscore(self):
        """Le préfixe est utilisé tel quel — convention Eve_ est recommandée mais pas imposée."""
        assert make_tablename("papi", "users") == "papiusers"

    def test_empty_name(self):
        assert make_tablename("eve_", "") == "eve_"

    def test_name_with_underscore(self):
        assert make_tablename("kif_", "user_accounts") == "kif_user_accounts"


# ---------------------------------------------------------------------------
# AmxConfig dataclass
# ---------------------------------------------------------------------------

class TestAmxConfig:
    """Tests de la dataclass AmxConfig."""

    def test_defaults(self):
        config = AmxConfig()
        assert config.name == ""
        assert config.route == "/"
        assert config.type == "api"
        assert config.module == ""
        assert config.table_prefix == ""
        assert config.dist_dir == "dist"
        assert config.version == "0.0.0"
        assert config.description == ""
        assert config.enabled is True
        assert isinstance(config.project_dir, Path)

    def test_api_config(self):
        config = AmxConfig(
            name="Eve-API",
            route="/eve",
            type="api",
            module="eve_api",
            table_prefix="eve_",
            version="1.0.0",
        )
        assert config.name == "Eve-API"
        assert config.type == "api"
        assert config.module == "eve_api"
        assert config.table_prefix == "eve_"

    def test_static_config(self):
        config = AmxConfig(
            name="Eve-UI",
            route="/eve",
            type="static",
            dist_dir="dist/spa",
        )
        assert config.type == "static"
        assert config.dist_dir == "dist/spa"
        assert config.module == ""  # non utilisé en mode static


# ---------------------------------------------------------------------------
# load_amx_config
# ---------------------------------------------------------------------------

class TestLoadAmxConfig:
    """Tests du chargement d'un amx.yaml depuis un package."""

    def test_load_missing_returns_empty(self, tmp_path: Path):
        """Si amx.yaml est introuvable, on retourne un AmxConfig vide (fail-safe)."""
        # tmp_path est vide : pas d'amx.yaml en vue
        config = load_amx_config(str(tmp_path / "fake_module" / "__init__.py"))
        assert config.name == ""
        assert config.module == ""

    def test_load_valid_yaml(self, tmp_path: Path):
        """Charge un amx.yaml valide situé juste à côté du package."""
        amx_content = textwrap.dedent("""
            name: My-API
            route: /my
            type: api
            module: my_api
            table_prefix: my_
            version: 2.0.0
            description: Une API de test
            enabled: true
        """).strip()
        (tmp_path / "amx.yaml").write_text(amx_content)

        # __init__.py du module est juste sous amx.yaml
        module_init = tmp_path / "my_api" / "__init__.py"
        module_init.parent.mkdir()
        module_init.touch()

        config = load_amx_config(str(module_init))
        assert config.name == "My-API"
        assert config.route == "/my"
        assert config.type == "api"
        assert config.module == "my_api"
        assert config.table_prefix == "my_"
        assert config.version == "2.0.0"
        assert config.description == "Une API de test"
        assert config.enabled is True
        assert config.project_dir == tmp_path

    def test_load_yaml_in_parent_directory(self, tmp_path: Path):
        """amx.yaml peut être 1 ou 2 niveaux au-dessus du module."""
        (tmp_path / "amx.yaml").write_text("name: Parent\n")
        nested = tmp_path / "v1" / "my_api"
        nested.mkdir(parents=True)
        (nested / "__init__.py").touch()

        config = load_amx_config(str(nested / "__init__.py"))
        assert config.name == "Parent"

    def test_load_invalid_yaml_returns_empty(self, tmp_path: Path, capsys):
        """Un YAML mal formé ne doit pas crasher — on retourne une config vide."""
        (tmp_path / "amx.yaml").write_text("name: 'unclosed quote")
        module_init = tmp_path / "my_api" / "__init__.py"
        module_init.parent.mkdir()
        module_init.touch()

        config = load_amx_config(str(module_init))
        # Erreur loggée mais pas d'exception
        assert config.name == ""  # pas chargé

    def test_load_yaml_ignores_unknown_fields(self, tmp_path: Path):
        """Les champs YAML inconnus sont ignorés (forward compat)."""
        (tmp_path / "amx.yaml").write_text(
            "name: Forward\nunknown_field: should_be_ignored\nmodule: my\n"
        )
        module_init = tmp_path / "my_api" / "__init__.py"
        module_init.parent.mkdir()
        module_init.touch()

        config = load_amx_config(str(module_init))
        assert config.name == "Forward"
        assert config.module == "my"
