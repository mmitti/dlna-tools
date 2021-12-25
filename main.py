from typing import Any, Dict, List, NamedTuple, Optional, Union
import click
from click.core import Option
import utils
from collections import namedtuple
import re
import glob
import os
import shutil
from dataclasses import dataclass, is_dataclass, asdict
import json
import subprocess
from mutagen.flac import FLAC
import mutagen.id3 as id3 

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
        print(f"{file} >> {new_name}")
        if not dry_run:
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
                print(f"{file_name} >> ../{disc_num}-{file_name}")
                if not dry_run:
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
                print(f"{file_name} >> {m.group(1)} {m.group(3)}")
                if not dry_run:
                    os.rename(file_path, os.path.join(root_path, dir_name, f"{m.group(1)} {m.group(3)}"))

@dataclass
class ExportConfiguration:
    name: str
    is_export: bool = True
    new_name: Optional[str] = None
    file_prefix: Optional[str] = None
    sud_directory: Optional[List[Any]] = None

def encode_export_config(obj):
    if is_dataclass(obj):
        return asdict(obj)
    return obj
    
def decode_export_config(data: Dict) -> ExportConfiguration:
    return ExportConfiguration(**data)

@main.command()
@click.argument("json_file")
@click.pass_obj
def gen_export_recipe(obj: Dict[str, Any], json_file: str):
    root_path = obj["root"]
    dirs = utils.find_dirs(root_path)
    def walk(dirs: Dict[str, Union[str, Dict]]):
        ret = []
        for k in dirs.keys():
            if isinstance(dirs[k], dict):
                ret.append(ExportConfiguration(k, True, None, None, walk(dirs[k])))
            else:
                ret.append(ExportConfiguration(k, True, None, None, None))
        return ret
    with open(json_file, "w") as f:
        json.dump(walk(dirs), f, default=encode_export_config, ensure_ascii=False, indent=2)

@main.command()
@click.argument("json_file")
@click.argument("dst_root")
@click.option('--sox', default='sox')
@click.pass_obj
def exec_export(obj: Dict[str, Any], json_file: str, dst_root: str, sox: str):
    dry_run = obj["dry_run"]
    root_path = obj["root"]
    configs: List[ExportConfiguration]
    with open(json_file, "r") as f:
        configs = json.load(f, object_hook=decode_export_config)

    def walk(config: ExportConfiguration, src_dir_name: str, dst_dir_name: str, file_name_prefix: str):
        if not config.is_export:
            return
        src_dir_name = os.path.join(src_dir_name, config.name)
        name = config.name
        if config.new_name is not None:
            name = config.new_name
        if len(name) != 0:
            dst_dir_name = f"{dst_dir_name}_{name}".strip("_")
        if config.file_prefix:
            file_name_prefix = f"{file_name_prefix}_{config.file_prefix}".strip("_")
        if config.sud_directory:
            for sub_config in config.sud_directory:
                walk(sub_config, src_dir_name, dst_dir_name, file_name_prefix)
        else:
            if file_name_prefix:
                file_name_prefix += "_"
            print(f"{src_dir_name} >> {dst_dir_name}/{file_name_prefix}<file_name>")
            if not dry_run:
                os.makedirs(os.path.join(dst_root, dst_dir_name), exist_ok=True)
            for file_path in utils.find_files(os.path.join(root_path, src_dir_name), ["mp3", "flac"]):
                file_name = os.path.basename(file_path)
                src_full_path = os.path.join(dst_root, dst_dir_name, f"{file_name_prefix}{file_name}")
                if not dry_run:
                    shutil.copyfile(os.path.join(root_path, file_path), src_full_path)
                if os.path.splitext(file_name)[1].lower() == ".flac":
                    new_file_name = f"{os.path.splitext(file_name)[0]}.mp3"
                    print(f"convert {file_name} to {new_file_name}")
                    if not dry_run:
                        converted_full_path = os.path.join(dst_root, dst_dir_name, f"{file_name_prefix}{new_file_name}")
                        subprocess.run([sox, src_full_path, "-C", "192", converted_full_path])
                        flac = FLAC(src_full_path)
                        mp3 = id3.ID3()
                        if "title" in flac:
                            mp3.add(id3.TIT2(encoding=id3.Encoding.UTF8, text=flac["title"][0]))
                            pass
                        if "album" in flac:
                            mp3.add(id3.TALB(encoding=id3.Encoding.UTF8, text=flac["album"][0]))
                            pass
                        if "date" in flac:
                            mp3.add(id3.TALB(encoding=id3.Encoding.UTF8, text=flac["date"][0]))
                            pass
                        if "artist" in flac:
                            mp3.add(id3.TPE1(encoding=id3.Encoding.UTF8, text=flac["artist"][0]))
                            pass
                        if len(flac.pictures) > 0:
                            mp3.add(id3.APIC(encoding=id3.Encoding.UTF8, mime=flac.pictures[0].mime, type=3, desc=flac.pictures[0].desc, data=flac.pictures[0].data))
                        mp3.save(converted_full_path)
                        os.remove(src_full_path)

    for config in configs:
        walk(config, "", "", "")

if __name__ == '__main__':
    main()
