#!/usr/bin/env python

import os
import re
import shutil
import sys
from argparse import ArgumentParser, BooleanOptionalAction, Namespace
from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE, Popen, run
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, Callable, Iterator

from msgpack import Unpacker, packb


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


def oldfiles_command(shada_path: Path, sort: bool) -> list[str]:
    st = "table.sort(old);" if sort else ""
    return [
        "nvim",
        "-Es",
        "-c",
        rf"""lua local old=vim.v.oldfiles ; {st} io.stdout:write(vim.fn.join(old,"\n").."\n")""",
        "-i",
        str(shada_path),
    ]


def list_oldfiles(shada_path: Path, sort: bool):
    run(oldfiles_command(shada_path, sort), check=True)


def get_oldfiles_from_fzf(shada_path: Path, sort: bool) -> list[bytes]:
    p1 = Popen(
        oldfiles_command(shada_path, sort),
        stdout=PIPE,
    )
    p2 = Popen(["fzf", "-m"], stdin=p1.stdout, stdout=PIPE)
    output, _ = p2.communicate()
    return output.splitlines()


@dataclass
class Entry:
    typ: int
    timestamp: int
    length: int
    data: Any

    @classmethod
    def from_iter(cls, unpacker: Iterator) -> "Entry | None":
        try:
            # SHADA_ENTRY_OBJECT_SEQUENCE from /usr/share/nvim/runtime/autoload/shada.vim
            typ = next(unpacker)
            timestamp = next(unpacker)
            length: int = next(unpacker)
            data = next(unpacker)
            return Entry(typ, timestamp, length, data)
        except StopIteration:
            return None

    def dump(self, fout: BinaryIO):
        chunk: list[bytes] = []
        for item in [self.typ, self.timestamp, self.length, self.data]:
            if packed := packb(item):
                chunk.append(packed)
            else:
                print(f"WARN: skipped some chunks: {self}")
                chunk = []
                break
        if chunk:
            fout.write(b"".join(chunk))

    def affects_oldfiles(self) -> bool:
        # SHADA_ENTRY_NAMES from /usr/share/nvim/runtime/autoload/shada.vim
        # 7: 'global_mark'
        # 8: 'jump'
        # 10: 'local_mark'
        # 11: 'change'
        return self.typ in [7, 8, 10, 11]

    def file_name(self) -> bytes:
        # key "f" corresponds to file name
        # SHADA_STANDARD_KEYS from /usr/share/nvim/runtime/autoload/shada.vim
        return self.data["f"]


def filter_oldfiles(
    fin: BinaryIO, fout: BinaryIO, preds: list[Callable[[bytes], bool]]
) -> set[bytes]:
    unpacker: Iterator = Unpacker(fin)
    deleted = set()
    while True:
        entry = Entry.from_iter(unpacker)
        if not entry:
            break
        if entry.affects_oldfiles():
            file_name = entry.file_name()
            if any(pred(file_name) for pred in preds):
                deleted.add(file_name)
                continue
        entry.dump(fout)
    return deleted


class MyNamespace(Namespace):
    gone: bool
    yes: bool
    fzf: bool
    sort: bool


def gen_argp() -> ArgumentParser:
    argp = ArgumentParser(
        description="delete items from Neovim oldfiles",
        epilog="You can also provide the items you want to delete using stdin. e.g. nvim-oldfiles-cleaner -l | grep hoo | nvim-oldfiles-cleaner",
    )
    argp.add_argument("-l", "--list", action="store_true", help="list oldfiles")
    argp.add_argument(
        "-g",
        "--gone",
        action="store_true",
        help="delete oldfiles that do not exist in filesystem",
    )
    argp.add_argument(
        "-y", "--yes", action="store_true", help="do not confirm before deleting"
    )
    argp.add_argument(
        "--fzf",
        action="store_true",
        help="delete oldfiles using fzf command. You can choose multiple items using TAB key.",
    )
    argp.add_argument(
        "-s",
        "--sort",
        action=BooleanOptionalAction,
        default=True,
        help="sort output of --list and --fzf options",
    )
    argp.add_argument(
        "PATTERNS",
        nargs="*",
        help="delete oldfiles that matches to the regular expressions",
    )
    return argp


def gen_preds(
    stdins: list[bytes], shada_path: Path, args: MyNamespace
) -> list[Callable[[bytes], bool]]:
    preds = []
    if args.list:
        list_oldfiles(shada_path, args.sort)
        sys.exit()
    if args.gone:
        preds.append(lambda x: not Path(x.decode()).exists())
    for pat in args.PATTERNS:
        p = re.compile(pat)
        preds.append(lambda x, p=p: p.search(x.decode()))
    if args.fzf:
        files = get_oldfiles_from_fzf(shada_path, args.sort)
        if not files:
            sys.exit()
        preds.append(lambda x: x in files)
    if stdins:
        preds.append(lambda x: x in stdins)

    return preds


def main():
    argp = gen_argp()
    isatty = sys.stdin.isatty()
    if isatty and len(sys.argv) == 1:
        argp.print_help()
        sys.exit()
    stdins = [] if isatty else [x.rstrip().encode() for x in sys.stdin]

    args = argp.parse_args(namespace=MyNamespace())
    shada_path = get_shada_path()
    preds = gen_preds(stdins, shada_path, args)

    tmp = NamedTemporaryFile(delete=False, prefix="nvim-oldfiles-cleaner.")
    tmp.close()
    have_to_delete_tmp = True
    try:
        os.chmod(tmp.name, 0o600)  # this is the default permission of shada file
        with shada_path.open("rb") as fin, open(tmp.name, "wb") as fout:
            deleted = sorted(list(filter_oldfiles(fin, fout, preds)))
        if not deleted:
            print("Nothing to delete.")
            sys.exit()
        if args.yes or not isatty:
            for item in deleted:
                print("Deleting: " + item.decode())
        else:
            print("Items to delete:")
            for item in deleted:
                print("  " + item.decode())
            answer = input("Really delete from oldfiles? [Y/n]: ")
            if answer.lower() not in ["", "y", "yes"]:
                sys.exit()
        backup = shada_path.parent / (shada_path.name + ".old")
        print(f"Shada backup: {backup}")
        shutil.move(shada_path, backup)
        shutil.move(tmp.name, shada_path)
        have_to_delete_tmp = False
        print("Done")
    finally:
        if have_to_delete_tmp:
            os.unlink(tmp.name)


if __name__ == "__main__":
    main()
