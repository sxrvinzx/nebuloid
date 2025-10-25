import asyncio
from pathlib import Path
import secrets
import shutil
import string
import time
import os

def clear_folder(path):
    for filename in os.listdir(path):
        file_path = os.path.join(path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # delete file or symlink
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # delete folder recursively
        except Exception as e:
            print(f'Failed to delete {file_path}: {e}')

def short_id(length=10):
    chars = string.ascii_letters + string.digits  # a–zA–Z0–9
    return ''.join(secrets.choice(chars) for _ in range(length))

class NebuloidStorage:
    def __init__(self):
        self.cache_files = {}

        self.files = {'private_key.pem': None, 'public_key.pem': None, 'manifest.neb': None}
        self.dirs = {'utils': None, 'plugins': None, 'cache': None}

        exts = [".neb", ".pem", ".json"]
        for root, dirs, files in os.walk('./nucleus'):
            for d in dirs:
                if d in self.dirs:
                    full_path = os.path.join(root, d)
                    print("Dir", d, ":", full_path)
                    if self.dirs[d] is not None:
                        print(f"Warning: Duplicate directory {d} found at {full_path}; already registered at {self.dirs[d]}")
                        print(f"Using the Last occurrence.")
                    self.dirs[d] = full_path

            # skip walking inside plugins
            if os.path.basename(root) == 'plugins':
                dirs[:] = []

            for f in files:
                if any(f.endswith(ext) for ext in exts):
                    if f in self.files:
                        print(f"Warning: Duplicate file {f} found at {os.path.join(root, f)}; already registered at {self.files[f]}")
                        print(f"Using the Last occurrence.")
                    self.files[os.path.basename(f)] = os.path.join(root, f)

        print("Registered files:", self.files)
        print("Registered dirs:", self.dirs)
    
    def mount(self):
        clear_folder(self.dir('cache'))
    
    async def maintenance_task(self):
        while True:
            for file_id, info in list(self.cache_files.items()):
                if time.time() - info['meta']['time'] > info['meta'].get('time_to_live'):  # expiry
                    try:
                        os.remove(info['file_path'])
                    except Exception as e:
                        print(f"Error deleting cached file {info['file_path']}: {e}")
                    del self.cache_files[file_id]
            await asyncio.sleep(60)

    def file(self, filename, mode='r'):
        if filename in self.files:
            return open(self.files[filename], mode)
        raise FileNotFoundError(f"File {filename} not found in storage.")

    def dir(self, dirname):
        if dirname in self.dirs:
            return Path(self.dirs[dirname])
        raise FileNotFoundError(f"Directory {dirname} not found in storage.")

    def make_file(self, meta, filename, content=None, mode='w', time_to_live=3600):
        meta = meta or {}
        print("Making file with meta:", meta)
        file_id = short_id()
        file_name = f"{file_id}_{meta.get('plugin') or 'Unknown'}_{filename}"

        file_path = os.path.join(self.dir('cache'), file_name)

        self.cache_files[file_id] = {"file_path": file_path, "file_name": filename, "meta": {**meta, "id": file_id, "time": time.time(), "time_to_live": time_to_live}}

        return file_id
    
    def open_file(self, file_id, mode='r'):
        if file_id in self.cache_files:
            file_info = self.cache_files[file_id]
            return open(file_info['file_path'], mode)
        raise FileNotFoundError(f"Cached file with ID {file_id} not found.")
    
    def get_file_path(self, file_id):
        if file_id in self.cache_files:
            file_info = self.cache_files[file_id]
            return file_info['file_path']
        raise FileNotFoundError(f"Cached file with ID {file_id} not found.")