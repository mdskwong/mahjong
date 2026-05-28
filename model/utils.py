from pathlib import Path
from typing import List, Tuple
import ast

# Mapping dictionary for Mahjong labels
LABEL_MAPPING = {
    "m1": "1萬",
    "m2": "2萬",
    "m3": "3萬",
    "m4": "4萬",
    "m5": "5萬",
    "m6": "6萬",
    "m7": "7萬",
    "m8": "8萬",
    "m9": "9萬",
    "s1": "1索",
    "s2": "2索",
    "s3": "3索",
    "s4": "4索",
    "s5": "5索",
    "s6": "6索",
    "s7": "7索",
    "s8": "8索",
    "s9": "9索",
    "t1": "1筒",
    "t2": "2筒",
    "t3": "3筒",
    "t4": "4筒",
    "t5": "5筒",
    "t6": "6筒",
    "t7": "7筒",
    "t8": "8筒",
    "t9": "9筒",
    "f1": "春",
    "f2": "夏",
    "f3": "秋",
    "f4": "冬",
    "f5": "梅",
    "f6": "蘭",
    "f7": "菊",
    "f8": "竹",
    "z1": "東",
    "z2": "南",
    "z3": "西",
    "z4": "北",
    "z5": "中",
    "z6": "發",
    "z7": "白",
}

LABEL_ID = [
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "m1",
    "m2",
    "m3",
    "m4",
    "m5",
    "m6",
    "m7",
    "m8",
    "m9",
    "s1",
    "s2",
    "s3",
    "s4",
    "s5",
    "s6",
    "s7",
    "s8",
    "s9",
    "t1",
    "t2",
    "t3",
    "t4",
    "t5",
    "t6",
    "t7",
    "t8",
    "t9",
    "z1",
    "z2",
    "z3",
    "z4",
    "z5",
    "z6",
    "z7",
]


def get_latest_model_path(train_root_path: Path) -> Path:
    # find the versions with the highest number in the train folder name
    train_versions = list(
        (
            int(train_folder_path.name.split("train")[-1])
            if train_folder_path.name != "train"
            else 1
        )
        for train_folder_path in train_root_path.glob("train*")
    )
    if len(train_versions) == 0:
        raise FileNotFoundError("No training folders found in the specified path.")

    return train_root_path / f"train{max(train_versions)}/weights/last.pt"


def download_data(version: int) -> None:
    from roboflow import Roboflow
    from dotenv import load_dotenv
    import os

    load_dotenv()

    rf = Roboflow(api_key=os.environ.get("API_KEY"))
    project = rf.workspace("mahjongdetect-6yabv").project("mahjong_detect")

    dataset = project.version(version).download("yolov11")


def load_config_file(config_path: Path) -> List[str]:
    with open(config_path, "r") as f:
        while True:
            line = f.readline()
            if not line:
                raise ValueError("Cannot find 'names' in the config file.")

            if line.startswith("names"):
                classes = ast.literal_eval(line.split("names:")[1])
                break

    return classes
