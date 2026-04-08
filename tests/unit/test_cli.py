"""Tests for the CLI application layer."""

from typer.testing import CliRunner

from wb.cli.app import app

runner = CliRunner()


class TestCLIApp:
    """Tests for the main CLI application."""

    def test_version_command(self):
        """Test version command outputs version string."""
        result = runner.invoke(app, ['version'])
        assert result.exit_code == 0
        assert 'wb-cli' in result.output

    def test_help_shows_commands(self):
        """Test help output lists expected command groups."""
        result = runner.invoke(app, ['--help'])
        assert result.exit_code == 0
        assert 'auth' in result.output
        assert 'version' in result.output

    def test_auth_help_shows_subcommands(self):
        """Test auth help lists expected subcommands."""
        result = runner.invoke(app, ['auth', '--help'])
        assert result.exit_code == 0
        assert 'login' in result.output
        assert 'logout' in result.output
        assert 'list' in result.output
        assert 'use' in result.output
        assert 'status' in result.output
        assert 'ping' in result.output
        assert 'login-portal' in result.output
        assert 'generate-token' in result.output
        assert 'categories' in result.output

    def test_global_options_exist(self):
        """Test global options are present in help."""
        result = runner.invoke(app, ['--help'])
        assert '--verbose' in result.output
        assert '--quiet' in result.output
        assert '--json' in result.output
        assert '--profile' in result.output

    def test_auth_list_empty(self):
        """Test auth list with no profiles shows guidance."""
        result = runner.invoke(app, ['auth', 'list'])
        assert result.exit_code == 0
        assert 'No profiles' in result.output or 'no profiles' in result.output.lower()

    def test_auth_status_no_profile(self):
        """Test auth status with no active profile."""
        result = runner.invoke(app, ['auth', 'status'])
        assert result.exit_code == 0


class TestCLIAuthLogin:
    """Tests for auth login command."""

    def test_login_help(self):
        """Test login help shows expected options."""
        result = runner.invoke(app, ['auth', 'login', '--help'])
        assert result.exit_code == 0
        assert '--token' in result.output
        assert '--profile' in result.output
        assert '--category' in result.output

    def test_login_requires_token(self):
        """Test login prompts for token when not provided."""
        result = runner.invoke(app, ['auth', 'login'], input='\n')
        # Should prompt for token
        assert 'token' in result.output.lower() or result.exit_code != 0
