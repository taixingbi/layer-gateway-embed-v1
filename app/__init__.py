from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("router-embed")
except PackageNotFoundError:
    __version__ = "0.0.0"
