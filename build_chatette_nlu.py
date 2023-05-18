
from pathlib import Path

from chatette.facade import Facade

def compile_chatette(root : Path):
    for master_chatette in root.rglob("*master.chatette"):
        if master_chatette.is_file() and master_chatette.name.split('.')[-1] == 'chatette':
            save_output_dir = master_chatette.parent.absolute().joinpath("output/")
            facade = Facade.reset_system(master_chatette, save_output_dir, adapter_str='rasa', force_overwriting=True)
            facade.run()

if __name__ == "__main__":
    compile_chatette(Path('./projects/'))
