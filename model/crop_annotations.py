from pathlib import Path
from collections import defaultdict
import argparse
from typing import List

import cv2

from utils import load_config_file


def create_classes_folders(output_folder: Path, classes: List[str]) -> None:
    # Create a directory to save cropped images
    output_folder.mkdir(exist_ok=True)
    for c in classes:
        class_folder = output_folder / c
        class_folder.mkdir(exist_ok=True)  # Create the class folder if it doesn't exist


def crop_images_from_folder(
    images_path: Path, labels_path: Path, output_folder: Path, classes: List[str]
) -> None:
    create_classes_folders(output_folder, classes)
    # Loop through each label file
    print(f"Cropping images from {images_path} to {output_folder}")
    for label_file in labels_path.glob("*.txt"):
        # Get the corresponding image file
        image_file = label_file.with_suffix(".jpg")
        image_path = images_path / image_file.name
        image = cv2.imread(str(image_path))

        if image is None:
            print(f"Warning: Could not read image {image_file.name}. Skipping.")
            continue

        # Read the label file
        with label_file.open("r") as f:
            added_labels = defaultdict(int)
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    class_id = int(parts[0])
                    x_center = float(parts[1]) * image.shape[1]
                    y_center = float(parts[2]) * image.shape[0]
                    width = float(parts[3]) * image.shape[1]
                    height = float(parts[4]) * image.shape[0]

                    # Calculate the top-left and bottom-right corner of the bounding box
                    x1 = int(x_center - width / 2)
                    y1 = int(y_center - height / 2)
                    x2 = int(x_center + width / 2)
                    y2 = int(y_center + height / 2)

                    # Crop the image
                    cropped_image = image[y1:y2, x1:x2]

                    if cropped_image.size == 0:
                        print(
                            f"Warning: Cropped image is empty for {image_file.name}. Skipping."
                        )
                        continue
                    cropped_image_path = (
                        output_folder
                        / classes[class_id]
                        / f"{image_file.stem}_{added_labels[classes[class_id]]}.jpg"
                    )
                    cv2.imwrite(str(cropped_image_path), cropped_image)

                    # increment the label count for the current class
                    added_labels[classes[class_id]] += 1
                else:
                    print(
                        f"Warning: Invalid label format in {label_file.name}. Skipping."
                    )

    print("Cropping completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="crop annotations from training and validation images in yolov11 format."
    )
    parser.add_argument("-i", "--in_path", type=str, help="path of the dataset folder.")
    args = parser.parse_args()

    dataset_path = Path(args.in_path)
    if not dataset_path.is_dir():
        raise ValueError(f"Invalid dataset path: {dataset_path}")

    train_folder_path = dataset_path / "train"
    valid_folder_path = dataset_path / "valid"
    config_file_path = dataset_path / "data.yaml"

    classes = load_config_file(config_file_path)

    crop_images_from_folder(
        train_folder_path / "images",
        train_folder_path / "labels",
        dataset_path / "train_cropped",
        classes,
    )
    crop_images_from_folder(
        valid_folder_path / "images",
        valid_folder_path / "labels",
        dataset_path / "valid_cropped",
        classes,
    )
