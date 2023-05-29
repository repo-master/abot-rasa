
import multiprocessing
from pathlib import Path
from typing import Tuple

from chatette.facade import Facade
from tqdm import tqdm


def compile_chatette(args: Tuple[Path, Path]):
    chatette_master_file, output_dir = args
    facade = Facade.reset_system(chatette_master_file, output_dir, adapter_str='rasayml', force_overwriting=True)
    facade.run()


def compile_chatette_dispatch(root: Path):
    pool = multiprocessing.Pool()

    convert_list = [
        (master_chatette, master_chatette.parent.absolute().joinpath("output/"))
        for master_chatette in root.rglob("*master.chatette")
        if master_chatette.is_file() and master_chatette.name.split('.')[-1] == 'chatette'
    ]

    list(tqdm(pool.imap_unordered(compile_chatette, convert_list), total=len(convert_list), unit='project'))

    pool.close()


if __name__ == "__main__":
    compile_chatette_dispatch(Path('./projects/'))
