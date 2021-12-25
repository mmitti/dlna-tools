import glob
import os
from typing import Dict, List, Union


def find_dirs(root: str) -> Dict[str, Union[str, Dict]]:
    dirs: Dict[str, Union[str, Dict]] = {}
    for g in glob.glob(f"{root}/**", recursive=True):
        if not os.path.isdir(g):
            continue
        if os.path.relpath(g, root) == ".":
            continue
        current_dir = dirs
        for p in os.path.relpath(g, root).split(os.path.sep):
            if not p in current_dir:
                current_dir[p] = {}
            current_dir = current_dir[p]
    
    def walk(dirs: Dict[str, Union[str, Dict]], path: str):
        for k in list(dirs.keys()):
            if len(dirs[k]) == 0:
                dirs[k] = os.path.join(path, k)
            else:
                walk(dirs[k], os.path.join(path, k))
    walk(dirs, "")
    return dirs
    
def find_files(dir_name: str, ext: List[str]):
    for path in glob.glob(os.path.join(dir_name, "*")):
        for e in ext:
            if os.path.splitext(path)[1].lower() == f".{e}":
                yield path 
# find_dirs("D:/zynq")
