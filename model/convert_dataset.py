import json
from pathlib import Path
from typing import Dict, Tuple, List
from dataclasses import dataclass

from utils import LABEL_ID

coco_names = [
    "t1",
    "t2",
    "t3",
    "t4",
    "t5",
    "t6",
    "t7",
    "t8",
    "t9",
    "s1",
    "s2",
    "s3",
    "s4",
    "s5",
    "s6",
    "s7",
    "s8",
    "s9",
    "m1",
    "m2",
    "m3",
    "m4",
    "m5",
    "m6",
    "m7",
    "m8",
    "m9",
    "z4",
    "z2",
    "z3",
    "z1",
    "z6",
    "z5",
    "z7",
]


@dataclass
class ImageMetadata:
    file_name: str
    height: int
    width: int


def convert_class(coco_class: int) -> int:
    # map coco class to mahjong
    return LABEL_ID.index(coco_names[coco_class])


def to_yolo_bbox(
    bbox: Tuple[float, float, float, float], img_height: int, img_width: int
) -> Tuple[float, float, float, float]:
    x_min, y_min, box_width, box_height = bbox

    # centre of the bounding box
    x_c = (x_min + x_min + box_width) // 2
    y_c = (y_min + y_min + box_height) // 2

    # convert the bounding box with respect to the image size
    x_c_rel = round(x_c / img_width, 3)
    y_c_rel = round(y_c / img_height, 3)
    w_rel = round(box_width / img_width, 3)
    h_rel = round(box_height / img_height, 3)

    return (x_c_rel, y_c_rel, w_rel, h_rel)


def write_yolo_txt(
    rel_bboxs: Tuple[float, float, float, float], img_class: int, write_path: Path
):
    with open(write_path, "a") as f:
        row = (
            f"{img_class} {rel_bboxs[0]} {rel_bboxs[1]} {rel_bboxs[2]} {rel_bboxs[3]}\n"
        )
        f.write(row)


class DatasetConverter:
    def __init__(self, dataset_dir: Path, coco_dataset_dir: Path):
        assert (
            dataset_dir.exists()
        ), f"Dataset directory '{dataset_dir}' does not exist."
        assert (
            coco_dataset_dir.exists()
        ), f"Coco dataset directory '{coco_dataset_dir}' does not exist."
        # get coco dataset annotations
        self.coco_json_file = (
            coco_dataset_dir / "annotations" / "instances_train2017.json"
        )
        assert (
            self.coco_json_file.exists()
        ), f"Coco json file does not exist at '{self.coco_json_file}'."

        self.dataset_dir = dataset_dir
        self.coco_dataset_dir = coco_dataset_dir
        self.ori_images_dir = coco_dataset_dir / "train2017"
        self.new_images_dir = self.dataset_dir / "train" / "images"
        self.new_labels_dir = dataset_dir / "train" / "labels"
        self.show_info()

    def show_info(self) -> None:
        print(f"Target Dataset directory: {self.dataset_dir.absolute()}")
        print(f"Coco dataset directory: {self.coco_dataset_dir.absolute()}")
        print(
            f"The images from the Coco dataset will move to: {self.new_images_dir.absolute()}"
        )
        print(
            f"The labels from the Coco dataset will move to: {self.new_labels_dir.absolute()}"
        )

    def convert(self) -> None:
        self.convert_annotations_to_yolo()
        self.relocate_images()

    def convert_annotations_to_yolo(self):
        img_metas, annotations = self.read_config()  # get image metadata

        for annotation in annotations:
            bbox = annotation["bbox"]

            # convert to yolo format
            rel_bbox = to_yolo_bbox(
                bbox,
                img_metas[annotation["image_id"]].height,
                img_metas[annotation["image_id"]].width,
            )
            # get class id of this annotation
            try:
                tile_class = convert_class(annotation["category_id"] - 1)
            except IndexError:
                print(
                    f"Invalid class id: {annotation['category_id']} from {img_metas[annotation["image_id"]].file_name}"
                )
                continue
            # and write annotations in YOLO format
            write_yolo_txt(
                rel_bbox,
                tile_class,
                write_path=(
                    self.new_labels_dir / img_metas[annotation["image_id"]].file_name
                ).with_suffix(".txt"),
            )

    def read_config(self) -> Tuple[Dict[int, ImageMetadata], List]:
        # read data from json
        with open(self.coco_json_file) as f:
            json_obj = json.load(f)
        return self.decode_json(json_obj)

    def relocate_images(self) -> None:
        print(f"Moving images to {self.new_images_dir}...")
        for img_file in self.ori_images_dir.iterdir():
            if img_file.is_file():
                img_file.rename(self.new_images_dir / img_file.name)

        print("Done moving images.")

    def decode_json(
        self,
        json_obj: Dict,
    ) -> Tuple[Dict[int, ImageMetadata], List]:
        metadata = {}
        for meta in json_obj["images"]:
            metadata[meta["id"]] = ImageMetadata(
                meta["file_name"], meta["height"], meta["width"]
            )
        return metadata, json_obj["annotations"]
