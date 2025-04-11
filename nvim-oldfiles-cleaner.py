#!/usr/bin/env python

import os
import re
import shutil
import sys
from argparse import ArgumentParser
from pathlib import Path
from subprocess import run, Popen, PIPE
from tempfile import NamedTemporaryFile
from typing import Callable


def get_shada_path() -> Path:
    # read `:help shada-file-name` to know where shada file is actually stored.
    # TODO: how can we detect when user changed the shada path?
    res = run(
        [
            "nvim",
            "-Es",
            "-c",
            """lua io.stdout:write(vim.fn.stdpath("state"))""",
        ],
        capture_output=True,
        check=True,
    )

    return Path(res.stdout.decode()) / "shada" / "main.shada"


def shada_to_text(shada_path: Path, out_path: Path):
    # Shada file is messagepack, but nvim can read it.
    # So we convert it to text by changing the `filetype` of the buffer.
    run(
        [
            "nvim",
            "-Es",
            "-c",
            f"e {shada_path} | set ft=text | w! {out_path}",
        ],
        check=True,
    )


def text_to_shada(text_path: Path, out_path: Path):
    run(
        [
            "nvim",
            "-Es",
            "-c",
            f"e {text_path} | set ft=shada | w! {out_path}",
        ],
        check=True,
    )


def oldfiles_command(shada_path: Path) -> list[str]:
    return [
        "nvim",
        "-Es",
        "-c",
        r"""lua io.stdout:write(vim.fn.join(vim.v.oldfiles,"\n").."\n")""",
        "-i",
        str(shada_path),
    ]


def list_oldfiles(shada_path: Path):
    run(oldfiles_command(shada_path))


def get_oldfiles_from_fzf(shada_path: Path) -> list[bytes]:
    p1 = Popen(
        oldfiles_command(shada_path),
        stdout=PIPE,
    )
    p2 = Popen(["fzf", "-m"], stdin=p1.stdout, stdout=PIPE)
    output, _ = p2.communicate()
    return output.splitlines()


def filter_oldfiles(
    path: Path, preds: list[Callable[[bytes], bool]]
) -> tuple[Path, set[bytes]]:
    FNH = b"  + f    file name"
    tmp = NamedTemporaryFile(delete=False, prefix="nvim-oldfiles-cleaner.")
    tmp.close()
    os.chmod(tmp.name, 0o600)
    deleted = set()
    with path.open("rb") as fin, open(tmp.name, "wb") as fout:
        cur = []
        printcur = True
        for line in fin:
            if line.startswith(FNH):
                fn = line.removeprefix(FNH).strip(b' "\n')
                if any(pred(fn) for pred in preds):
                    deleted.add(fn)
                    printcur = False
                cur.append(line)

            elif line.startswith(b"  "):
                assert cur is not None
                cur.append(line)
            else:
                if printcur:
                    for c in cur:
                        fout.write(c)
                cur = [line]
                printcur = True
        if printcur:
            for c in cur:
                fout.write(c)
    return (Path(tmp.name), deleted)


def shada_to_tmp(shada_path: Path) -> Path:
    tmp = NamedTemporaryFile(delete=False, prefix="nvim-oldfiles-cleaner.")
    tmp.close()
    os.chmod(tmp.name, 0o600)
    tpath = Path(tmp.name)
    shada_to_text(shada_path, tpath)
    return tpath


def argument_parser() -> ArgumentParser:
    argp = ArgumentParser(description="delete items from Neovim oldfiles")
    argp.add_argument("-l", "--list", action="store_true", help="list oldfiles")
    argp.add_argument(
        "-g",
        "--gone",
        action="store_true",
        help="delete oldfiles that do not exist in filesystem",
    )
    argp.add_argument(
        "-f",
        "--fzf",
        action="store_true",
        help="delete oldfiles using fzf command. You can choose multiple items using TAB key.",
    )
    argp.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="do not confirm before deleting",
    )
    argp.add_argument(
        "PATTERNS",
        nargs="*",
        help="delete oldfiles that matches to the regular expressions",
    )
    return argp


def main():
    argp = argument_parser()
    if len(sys.argv) == 1:
        argp.print_help()
        sys.exit()
    args = argp.parse_args()
    shada_path = get_shada_path()
    preds = []
    if args.list:
        list_oldfiles(shada_path)
        sys.exit()
    if args.gone:
        preds.append(lambda x: not Path(x.decode()).exists())
    for pat in args.PATTERNS:
        p = re.compile(pat)
        preds.append(lambda x, p=p: p.search(x.decode()))
    if args.fzf:
        files = get_oldfiles_from_fzf(shada_path)
        if not files:
            sys.exit()
        preds.append(lambda x: x in files)
    tpath = shada_to_tmp(shada_path)
    try:
        filtered, deleted = filter_oldfiles(tpath, preds)
        if not deleted:
            print("no item to delete")
            sys.exit()
        elif not args.yes:
            print("Items to delete:")
            for item in deleted:
                print("  " + item.decode())
            answer = input("Really delete from oldfiles? [Y/n]: ")
            if answer.lower() not in ["", "y", "yes"]:
                sys.exit()
    finally:
        tpath.unlink()

    try:
        backup = str(shada_path) + ".old"
        print(f"Shada backup: {backup}")
        shutil.move(shada_path, backup)
        text_to_shada(filtered, shada_path)
        print("Completed.")
    finally:
        if filtered:
            filtered.unlink()


if __name__ == "__main__":
    main()
