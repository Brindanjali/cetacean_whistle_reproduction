"""WhistleCode command line (PLAN.md section 10). Run from anywhere; nothing needs installing beyond requirements.txt.

P1 commands (the whistle alphabet):

    python whistlecode/whistlecode.py build-codebook [--quick]
        choose the 16 symbol types and the signature whistle from the VAE-GMM (PLAN.md section 5); about 20-40 min.
        --quick: a few sends only, written to whistlecode/outputs/codebook_quick, to check that everything runs

    python whistlecode/whistlecode.py show-codebook [--quick]
        list the codebook's types and verification results (refuses a codebook built from other model files)

P0 commands (no audio):

    python whistlecode/whistlecode.py frame "HI" --key reef42 [--nonce 7]
        show how a message is framed: bytes, parity, whistle symbols, whistle count, rough airtime

    python whistlecode/whistlecode.py roundtrip "MEET AT DAWN" --key reef42 --wrong 3 --erased 5 [--seed 0]
        frame a message, damage some whistle symbols (wrong or erased), decode, and report what was repaired;
        without --nonce the nonce comes from --seed, so the same command always gives the same result
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

import numpy as np  # noqa: E402

from wcode import framing  # noqa: E402
from wcode.config import ConfigError, WhistleCodeError, default_config, payload_parity  # noqa: E402,F401


def _fmt(symbols) -> str:
    return " ".join("-" if s == framing.ERASED else f"{int(s):x}" for s in symbols)


def _show_frame(fr: framing.Frame, cfg: dict) -> None:
    k = framing.payload_k(fr.length, cfg)
    nsym = payload_parity(k, cfg)
    c = framing.frame_counts(fr.length, cfg)
    lo, hi = cfg["schedule"]["interval_s"]
    text = fr.payload.decode("utf-8", errors="replace")
    print(f"message  : {text!r} ({fr.length} bytes)")
    print(f"nonce    : {fr.nonce}")
    print(f"header   : length + nonce, {cfg['fec']['header_parity']} parity bytes -> {len(fr.header_codeword)} bytes"
          f" -> {c['header']} whistles")
    print(f"payload  : {fr.length} + 2 CRC = {k} bytes, {nsym} parity bytes -> {len(fr.payload_codeword)} bytes"
          f" -> {c['payload']} whistles")
    print(f"whistles : {c['preamble']} preamble + {c['header']} header + {c['payload']} payload = {c['total']}")
    print(f"airtime  : about {c['total'] * (lo + hi) / 2:.0f} s at the mean interval of {(lo + hi) / 2:.2f} s")
    print(f"header symbols  : {_fmt(fr.header_symbols)}")
    print(f"payload symbols : {_fmt(fr.payload_symbols)}")


def _byte_damage(sent, got) -> tuple[int, int]:
    """(wrong bytes, erased bytes) between two symbol sequences of one codeword."""
    a = np.asarray(sent).reshape(-1, 2)
    b = np.asarray(got).reshape(-1, 2)
    erased = (b == framing.ERASED).any(axis=1)
    wrong = (~erased) & (a != b).any(axis=1)
    return int(wrong.sum()), int(erased.sum())


def cmd_frame(args) -> int:
    cfg = default_config()
    _show_frame(framing.encode(args.message, args.key, args.nonce, cfg), cfg)
    return 0


def cmd_roundtrip(args) -> int:
    cfg = default_config()
    rng = np.random.default_rng(args.seed)
    nonce = int(rng.integers(256)) if args.nonce is None else args.nonce     # same --seed, same run
    fr = framing.encode(args.message, args.key, nonce, cfg)
    sent = fr.symbols
    nh = len(fr.header_symbols)
    pool = {"all": np.arange(len(sent)), "header": np.arange(nh), "payload": np.arange(nh, len(sent))}[args.where]
    if args.wrong + args.erased > len(pool):
        print(f"only {len(pool)} whistles to damage in '{args.where}'", file=sys.stderr)
        return 2
    got = sent.copy()
    pos = rng.choice(pool, args.wrong + args.erased, replace=False)
    for p in pos[:args.wrong]:
        got[p] = (sent[p] + rng.integers(1, 16)) % 16          # a different symbol: a misclassified whistle
    got[pos[args.wrong:]] = framing.ERASED                      # a missed or doubtful whistle
    _show_frame(fr, cfg)
    print(f"\ndamaged  : {args.wrong} wrong + {args.erased} erased whistles (seed {args.seed}, where = {args.where})")
    print(f"received : {_fmt(got)}")
    he, hf = _byte_damage(sent[:nh], got[:nh])
    pe, pf = _byte_damage(sent[nh:], got[nh:])
    hp = int(cfg["fec"]["header_parity"])
    pp = payload_parity(framing.payload_k(fr.length, cfg), cfg)
    print(f"header   : {he} wrong + {hf} erased bytes -> 2e + f = {2 * he + hf} (repairable up to {hp})")
    print(f"payload  : {pe} wrong + {pf} erased bytes -> 2e + f = {2 * pe + pf} (repairable up to {pp})")
    try:
        header, msg = framing.decode(got, args.key, cfg)
    except framing.DecodeError as e:
        print(f"result   : FAILED at {e.stage} ({e.detail})")
        return 1
    ok = msg.payload == fr.payload
    shown = msg.text if msg.text is not None else msg.payload.hex()
    print(f"result   : {'OK' if ok else 'WRONG'} -> {shown!r}"
          f" (header repaired {header.n_errors} wrong + {header.n_erasures} erased bytes,"
          f" payload {msg.n_errors} wrong + {msg.n_erasures} erased)")
    return 0 if ok else 1


def cmd_build_codebook(args) -> int:
    from wcode import codebook

    info = codebook.build(default_config(), quick=args.quick, log=lambda m: print(m, flush=True))
    return 0 if info["verification"]["passed"] else 1


def cmd_show_codebook(args) -> int:
    from wcode import codebook

    cfg = default_config()
    cb = codebook.load(cfg, codebook.out_dir(cfg, args.quick))
    v = cb.info["verification"]
    print(f"codebook built {cb.info['created_utc']} from {cb.info['model']['checkpoint']} "
          f"(sha256 {cb.info['model']['checkpoint_sha256'][:12]}...){'  [QUICK]' if cb.info['quick'] else ''}")
    print(f"verification: {'PASSED' if v['passed'] else 'FAILED'}, worst pair {v['worst_pair']:.1%}, "
          f"errors {v['error_rate']:.1%}, erasures {v['erasure_rate']:.1%} ({v['sends_per_type']} sends per type)")
    print(" symbol  component   N_k  duration  span_Hz  detected  correct  erased  worst_pair")
    for t in [*cb.info["types"], cb.info["signature"]]:
        sym = "sig" if t["symbol"] is None else f"{t['symbol']:x}"
        print(f"  {sym:>5}  {t['component']:9d}  {t['nk']:5.0f}  {t['duration_ms']:6.0f} ms  {t['span_hz']:7.0f}"
              f"  {t['detection_rate']:8.1%}  {t['accuracy']:7.1%}  {t['erasure_rate']:6.1%}  {t['worst_pair']:9.1%}")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")       # Windows consoles cannot print every character
    p = argparse.ArgumentParser(prog="whistlecode", description="WhistleCode: hide text messages in whistles")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, hlp in (("build-codebook", cmd_build_codebook, "choose the whistle types (PLAN.md section 5)"),
                          ("show-codebook", cmd_show_codebook, "list the codebook's types and verification")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--quick", action="store_true", help="the quick check build in outputs/codebook_quick")
        s.set_defaults(fn=fn)
    for name, fn, hlp in (("frame", cmd_frame, "show how a message is framed into whistle symbols"),
                          ("roundtrip", cmd_roundtrip, "frame, damage whistles, decode")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("message", help="text to send")
        s.add_argument("--key", required=True, help="shared key")
        s.add_argument("--nonce", type=int, default=None,
                       help="0-255; when left out, random for frame and drawn from --seed for roundtrip")
        s.set_defaults(fn=fn)
        if name == "roundtrip":
            s.add_argument("--wrong", type=int, default=0, help="whistles classified as the wrong symbol")
            s.add_argument("--erased", type=int, default=0, help="whistles missed or too doubtful to classify")
            s.add_argument("--where", choices=("all", "header", "payload"), default="all")
            s.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (framing.FramingError, ValueError, WhistleCodeError) as e:     # config, model-file and codebook errors
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
