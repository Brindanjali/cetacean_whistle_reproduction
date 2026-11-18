"""config.toml: the values PLAN.md fixes, and the checks that refuse a config the code cannot honour."""
import pytest

from wcode.config import ConfigError, default_config, load_config, payload_parity, validate


def test_plan_values(cfg):
    assert cfg["framing"]["max_payload_bytes"] == 140
    assert cfg["framing"]["n_preamble"] == 3
    assert cfg["framing"]["bits_per_symbol"] == 4
    assert cfg["fec"]["header_parity"] == 4
    assert cfg["fec"]["library_version"] == "1.7.0"
    assert cfg["keys"]["header_streams"] == ["scrambler", "timing", "pitch", "position"]
    assert cfg["keys"]["payload_streams"] == ["scrambler", "timing", "pitch", "variation", "position"]


@pytest.mark.parametrize("k, nsym", [(3, 8), (4, 8), (16, 8), (17, 9), (22, 11), (142, 71)])
def test_payload_parity_rule(cfg, k, nsym):
    assert payload_parity(k, cfg) == nsym


def test_longest_payload_fits_one_codeword(cfg):
    k = cfg["framing"]["max_payload_bytes"] + 2
    assert k + payload_parity(k, cfg) == 213 <= 255


def test_default_config_is_a_copy():
    a = default_config()
    a["framing"]["max_payload_bytes"] = 1
    assert default_config()["framing"]["max_payload_bytes"] == 140


@pytest.mark.parametrize("section, key, value", [
    ("framing", "bits_per_symbol", 5),
    ("framing", "max_payload_bytes", 200),          # 202 + 101 parity > 255
    ("framing", "min_payload_bytes", 0),
    ("framing", "crc", "CRC-32"),
    ("fec", "header_parity", 3),
    ("fec", "library_version", "9.9.9"),
    ("keys", "payload_streams", ["timing"]),
])
def test_validate_rejects(cfg, section, key, value):
    cfg[section][key] = value
    with pytest.raises(ConfigError):
        validate(cfg)


def test_load_config_reads_the_file():
    assert load_config()["schema_version"] == 1
