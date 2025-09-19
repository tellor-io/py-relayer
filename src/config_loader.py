import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# toml parsing: use tomllib on 3.11+, fallback to tomli
try:
    import tomllib  # type: ignore
    _TOML_LOAD = tomllib.load
except Exception:  # pragma: no cover
    try:
        import tomli  # type: ignore
        _TOML_LOAD = tomli.load
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "TOML parser not available. Install Python 3.11+ or add 'tomli' to requirements."
        ) from e


DEFAULT_SEARCH_ROOT = Path.cwd() / "configs"


def _read_toml(path: Path) -> Dict[str, Any]:
    with open(path, "rb") as f:
        return _TOML_LOAD(f)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)  # type: ignore[index]
        else:
            result[key] = value
    return result


def _resolve_config_ref(ref: str) -> Path:
    p = Path(ref).expanduser()
    if p.is_dir():
        # treat directory as directory-containing config named config.toml
        candidate = p / "config.toml"
        if candidate.exists():
            return candidate
    if p.suffix == "":
        # try as explicit file path with .toml
        if p.exists() and p.is_file():
            return p
        candidate = p.with_suffix(".toml")
        if candidate.exists():
            return candidate
    else:
        if p.exists():
            return p

    # search under DEFAULT_SEARCH_ROOT allowing subdirs
    # ref like "saga/eth-usd" -> configs/saga/eth-usd.toml
    root_candidate = DEFAULT_SEARCH_ROOT / ref
    if root_candidate.suffix == "":
        root_candidate = root_candidate.with_suffix(".toml")
    if root_candidate.exists():
        return root_candidate

    raise FileNotFoundError(f"Config '{ref}' not found (searched direct path and {DEFAULT_SEARCH_ROOT})")


def _interpolate_env(env_map: Dict[str, Any]) -> Dict[str, str]:
    interpolated: Dict[str, str] = {}
    for k, v in env_map.items():
        s = str(v)
        interpolated[k] = os.path.expandvars(s)
    return interpolated


def _load_with_inheritance(path: Path, visited: Optional[Set[Path]] = None, depth: int = 0) -> Dict[str, Any]:
    if visited is None:
        visited = set()
    if depth > 16:
        raise RuntimeError("Config inheritance depth exceeded safe limit (16)")
    norm = path.resolve()
    if norm in visited:
        raise RuntimeError(f"Cyclic config inheritance detected at {norm}")
    visited.add(norm)

    cfg = _read_toml(norm)

    # Support both 'parent' (string or list) and 'extends' (list) for inheritance
    parents: List[str] = []
    parent_field = cfg.get("parent")
    if isinstance(parent_field, str):
        parents.append(parent_field)
    elif isinstance(parent_field, list):
        parents.extend([str(x) for x in parent_field])

    extends_field = cfg.get("extends")
    if isinstance(extends_field, list):
        parents.extend([str(x) for x in extends_field])

    merged: Dict[str, Any] = {}
    for ref in parents:
        parent_path = _resolve_config_ref(ref)
        parent_cfg = _load_with_inheritance(parent_path, visited, depth + 1)
        merged = _deep_merge(merged, parent_cfg)

    # Finally merge current
    merged = _deep_merge(merged, cfg)
    return merged


def load_config(config_ref: Optional[str]) -> Dict[str, Any]:
    if not config_ref:
        return {}
    path = _resolve_config_ref(config_ref)
    cfg = _load_with_inheritance(path)
    # Normalize top-level keys used by CLI
    if "env" not in cfg:
        cfg["env"] = {}
    if "commands" not in cfg:
        cfg["commands"] = {}
    return cfg


def apply_env(cfg: Dict[str, Any]) -> None:
    env_map = cfg.get("env", {}) or {}
    interpolated = _interpolate_env(env_map)
    for k, v in interpolated.items():
        os.environ[k] = v


def build_default_map(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Click default_map expects a mapping from command name to its defaults mapping
    # Our schema uses [commands.<name>] directly compatible
    commands = cfg.get("commands", {}) or {}
    # Ensure all values are plain dicts (Click requirement)
    out: Dict[str, Any] = {}
    for cmd, params in commands.items():
        if isinstance(params, dict):
            out[cmd] = dict(params)
    return out


