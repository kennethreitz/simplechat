import os
import pathlib
from appdirs import AppDirs

_NAME = "simplechat"
_AUTHOR = "simplechat"
_DEFAULT_DB_NAME = "simplechat.db"


def get_app_dir():
    """Returns the AppDirs object for the application."""

    return AppDirs(_NAME, _AUTHOR)


def mkdir_p(path):
    """Create a directory if it doesn't exist."""

    if not os.path.exists(path):
        return os.makedirs(path)


def get_config_dir():
    """Returns the full path to the configuration directory."""

    appdir = get_app_dir()
    config_dir = appdir.user_config_dir

    # Make the directory, if it doesn't exist.
    mkdir_p(config_dir)

    return pathlib.Path(appdir.user_config_dir)


def get_db_path():
    """Returns the full path to the database file."""

    config_dir = get_config_dir()
    return config_dir / _DEFAULT_DB_NAME


if __name__ == "__main__":
    print(get_db_path())
