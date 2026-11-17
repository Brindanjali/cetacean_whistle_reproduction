"""Load and check whistlecode/config.toml (PLAN.md section 13 lists the [DECISION] values it holds)."""
from __future__ import annotations

import copy
import functools
import math
import tomllib
from importlib import metadata
from pathlib import Path

WC_ROOT = Path(__file__).resolve().parents[1]      # whistlecode/
PROJECT_ROOT = WC_ROOT.parent                      # the repository root (the reproduction)
CONFIG_PATH = WC_ROOT / "config.toml"

SUPPORTED = {
    "schema_version": 1,
    "crc": "CRC-16/CCITT-FALSE",
    "crc_bytes": 2,
    "bits_per_symbol": 4,
    "symbol_order": "high_nibble_first",
    "header_data_bytes": 2,
    "nonce_bytes": 1,
    "library": "reedsolo",
}
RS_MAX_N = 255                                     # GF(2^8): at most 255 bytes per codeword


class ConfigError(RuntimeError):
    pass


def payload_parity(k: int, cfg: dict) -> int:
    """nsym for k payload bytes (message + CRC): max(payload_parity_min, ceil(k * payload_parity_ratio))."""
    f = cfg["fec"]
    return max(int(f["payload_parity_min"]), math.ceil(k * float(f["payload_parity_ratio"])))


def validate(cfg: dict, check_library: bool = True) -> None:
    def need(cond: bool, msg: str) -> None:
        if not cond:
            raise ConfigError(f"whistlecode config: {msg}")

    k, fr, fe = cfg.get("keys", {}), cfg.get("framing", {}), cfg.get("fec", {})
    need(cfg.get("schema_version") == SUPPORTED["schema_version"], "schema_version must be 1")
    need(fr.get("crc") == SUPPORTED["crc"] and int(fr.get("crc_bytes", 0)) == SUPPORTED["crc_bytes"],
         f"only {SUPPORTED['crc']} (2 bytes) is implemented")
    need(int(fr.get("bits_per_symbol", 0)) == SUPPORTED["bits_per_symbol"], "only 4 bits per symbol (M = 16) is implemented")
    need(fr.get("symbol_order") == SUPPORTED["symbol_order"], "only high_nibble_first is implemented")
    need(int(fr.get("header_data_bytes", 0)) == SUPPORTED["header_data_bytes"], "the header carries exactly length + nonce")
    need(int(k.get("nonce_bytes", 0)) == SUPPORTED["nonce_bytes"], "the nonce is exactly one byte")
    need(fr.get("text_encoding") == "utf-8", "text_encoding must be utf-8")
    need(int(fr.get("n_preamble", 0)) >= 1, "n_preamble must be at least 1")
    lo, hi = int(fr.get("min_payload_bytes", 0)), int(fr.get("max_payload_bytes", 0))
    need(1 <= lo <= hi <= 255, "need 1 <= min_payload_bytes <= max_payload_bytes <= 255 (the header's length byte)")
    k_max = hi + int(fr["crc_bytes"])
    need(k_max + payload_parity(k_max, cfg) <= RS_MAX_N,
         f"max_payload_bytes {hi} needs {k_max + payload_parity(k_max, cfg)} bytes, more than one codeword ({RS_MAX_N})")
    hp = int(fe.get("header_parity", 0))
    need(hp >= 2 and hp % 2 == 0, "header_parity must be an even number >= 2")
    need(int(fe.get("payload_parity_min", 0)) >= 2, "payload_parity_min must be >= 2")
    need(0 <= int(fe.get("erased_fill", -1)) <= 255, "erased_fill must be a byte value")
    for part in ("header_streams", "payload_streams"):
        names = list(k.get(part, []))
        need(names and len(names) == len(set(names)), f"keys.{part} must be non-empty and unique")
        need("scrambler" in names, f"keys.{part} must include 'scrambler'")
    need(isinstance(k.get("domain"), str) and k["domain"], "keys.domain must be a non-empty string")
    need(fe.get("library") == SUPPORTED["library"], "only the reedsolo library is supported")
    if check_library:
        try:
            have = metadata.version("reedsolo")
        except metadata.PackageNotFoundError as e:
            raise ConfigError("reedsolo is not installed (see whistlecode/requirements.txt)") from e
        need(have == fe.get("library_version"),
             f"reedsolo {have} is installed but config.toml pins {fe.get('library_version')}")


def load_config(path: str | Path | None = None, check_library: bool = True) -> dict:
    p = Path(path) if path else CONFIG_PATH
    cfg = tomllib.loads(p.read_text(encoding="utf-8"))
    validate(cfg, check_library)
    return cfg


@functools.lru_cache(maxsize=1)
def _default() -> dict:
    return load_config()


def default_config() -> dict:
    """The checked config.toml, loaded once; a copy, so callers may change it freely."""
    return copy.deepcopy(_default())
