from typing import Any, Dict, List, NamedTuple, Union
import click
import utils
from collections import namedtuple
import re
import glob
import os
import shutil


@click.group()
@click.option('--dry-run', is_flag=True)
@click.option('--root', default='.')
@click.pass_context
def main(ctx: click.Context, dry_run: bool, root: str):
    ctx.obj = {
        "dry_run": dry_run, 
        "root": root
    }


def remove_disc_prefix(dir: str, dry_run: bool=False):
    disc_num: int = None
    # check
    files: List[str] = []
    for file_path in utils.find_files(dir, ["mp3", "flac"]):
        file_name = os.path.basename(file_path)
        m = re.match(r"^(\d)-\d\d.+$", file_name)
        if m:
            files.append(file_name)
            if disc_num is None:
                disc_num = int(m.group(1))
            elif not file_name.startswith(f"{disc_num}-"):
                return
    for file in files:
        new_name = file.split(f"{disc_num}-", 1)[1]
        if dry_run:
            print(f"{file} >> {new_name}")
        else:
            os.rename(os.path.join(dir, file), os.path.join(dir, new_name))

@main.command()
@click.pass_obj
def remove_disc_dir(obj: Dict[str, Any]):
    dry_run = obj["dry_run"]
    root_path = obj["root"]
    dirs = utils.find_dirs(root_path)
    print("REMOVE DISC/DISK DIR")
    DiscTarget = NamedTuple("DiscTarget", [("root_dir", str), ("sub_dirs", List[str]), ("disc_numbers", List[int])])
    disc_targets: List[DiscTarget] = []
    
    def walk(dirs: Dict[str, Union[str, Dict]], path: str):
        t = DiscTarget(path, [], [])
        for k in dirs.keys():
            m = re.match(r"^[Dd][Ii][Ss][KkCc][ ]?([\d]+)$", k)
            if m and isinstance(dirs[k], str):
                t.sub_dirs.append(dirs[k])
                t.disc_numbers.append(int(m.group(1)))
            elif isinstance(dirs[k], dict):
                walk(dirs[k], os.path.join(path, k))
        if len(t.sub_dirs) > 0:
            disc_targets.append(t)
    walk(dirs, "")
    
    for target in disc_targets:
        for sub_dir, disc_num in zip(target.sub_dirs, target.disc_numbers):
            # 前処理
            remove_disc_prefix(os.path.join(root_path, sub_dir), dry_run)
            for file_path in utils.find_files(os.path.join(root_path, sub_dir), ["mp3", "flac"]):
                file_name = os.path.basename(file_path)
                if dry_run:
                    print(f"{file_name} >> ../{disc_num}-{file_name}")
                else:
                    os.rename(file_path, os.path.join(root_path, target.root_dir, f"{disc_num}-{file_name}"))
            if not dry_run:
                shutil.rmtree(os.path.join(root_path, sub_dir))

@main.command()
@click.pass_obj
def convert_file_name(obj: Dict[str, Any]):
    dry_run = obj["dry_run"]
    root_path = obj["root"]
    dirs = utils.find_dirs(root_path)
    print("CONVERT FILE NAME")
    dirs_flatten: List[str] = []
    def walk(dirs: Dict[str, Union[str, Dict]], path: str):
        for k in dirs.keys():
            if isinstance(dirs[k], dict):
                walk(dirs[k], os.path.join(path, k))
            else:
                dirs_flatten.append(os.path.join(path, k))
    walk(dirs, "")
    for dir_name in dirs_flatten:
        remove_disc_prefix(os.path.join(root_path, dir_name), dry_run)
        for file_path in utils.find_files(os.path.join(root_path, dir_name), ["mp3", "flac"]):
            file_name = os.path.basename(file_path)
            m = re.match(r"^((\d+-)?\d{2})-(.+)$", file_name)
            if m:
                if dry_run:
                    print(f"{file_name} >> {m.group(1)} {m.group(3)}")
                else:
                    os.rename(file_path, os.path.join(root_path, dir_name, f"{m.group(1)} {m.group(3)}"))

if __name__ == '__main__':
    main()
