from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from ultralytics.engine.results import Results
import cv2
from PIL import Image

from utils import LABEL_ID, LABEL_MAPPING

MIN_NUM_WINNING_TILES = 14


@dataclass
class WinningHand:
    centers: NDArray
    boxes: NDArray
    labels_id: NDArray

    def __post_init__(self):
        sorted_left_to_right = np.argsort(self.centers[:, 0])
        self.centers = self.centers[sorted_left_to_right]
        self.boxes = self.boxes[sorted_left_to_right]
        self.labels_id = self.labels_id[sorted_left_to_right].astype(int)

    @property
    def labels(self) -> List[str]:
        return [LABEL_ID[label_id] for label_id in self.labels_id]

    def __str__(self):
        return "Winning hand: " + " ".join(
            LABEL_MAPPING[label] for label in self.labels
        )


class WinningHandLocator:
    def __init__(
        self,
        results: Results,
        *,
        confidence_threshold: float = 0,
    ) -> None:
        if results.boxes is None:
            raise ValueError("No bounding boxes found in the results.")
        self.c_xy = results.boxes.xywh.cpu().numpy()[:, :2]
        self.c_xyn = results.boxes.xywhn.cpu().numpy()[:, :2]
        self.conf = results.boxes.conf.cpu().numpy()
        self.xyxy = results.boxes.xyxy.cpu().numpy()
        self.class_id = results.boxes.cls.cpu().numpy()

        # filter detections based on confidence threshold
        filtered_indices = self.conf >= confidence_threshold
        self.c_xyn = self.c_xyn[filtered_indices]
        self.conf = self.conf[filtered_indices]
        self.xyxy = np.round(self.xyxy[filtered_indices]).astype(int)
        self.class_id = self.class_id[filtered_indices]

        self.winning_hand = None

    def find_winning_hand(
        self,
        *,
        n_iter: int = 40,
        threshold: float = 0.01,
        y_checking_range: Optional[float] = None,
    ) -> Optional[WinningHand]:
        """find a set of detected tiles where their centers are colinera

        Args:
            n_iter (int, optional): number of iterations to find a winning hand. Defaults to 10.
            threshold (float, optional): y-distance threshold for being treated as a winning hand. Defaults to 0.01.
            y_checking_range (float, optional): normalized y range for tiles to be considered as possible winning hand. Decide automatically if not given.

        Returns:
            WinningHand
        """
        if y_checking_range is None:
            # automatically decide the range by ensuring that enough tiles detected
            for y_checking_range in (0.5, 0.25, 0):
                valid_detections = self.c_xyn[:, 1] > y_checking_range
                if np.count_nonzero(valid_detections) >= MIN_NUM_WINNING_TILES:
                    break
        else:
            assert (
                0 <= y_checking_range <= 1
            ), "y_checking_range must be between 0 and 1"

        valid_detections = self.c_xyn[:, 1] > y_checking_range
        n_valid_detections = np.count_nonzero(valid_detections)
        if n_valid_detections < MIN_NUM_WINNING_TILES:
            # insufficient valid detections that cause the winning hand
            return None
        if n_valid_detections >= 2 * MIN_NUM_WINNING_TILES:
            print(
                f"Warning: Using {y_checking_range=} will result in {n_valid_detections} detections, the algorithm wlll not work properly"
            )

        # estimate the winning hand location using RANSAC
        self.best_model, inliers_indices = RANSAC(
            self.c_xyn[valid_detections],
            metric=mean_squared_error,
            n_iter=n_iter,
            threshold=threshold,
        )
        if self.best_model:
            self.winning_hand = WinningHand(
                self.c_xyn[valid_detections][inliers_indices],
                self.xyxy[valid_detections][inliers_indices],
                self.class_id[valid_detections][inliers_indices],
            )

            return self.winning_hand

        return None

    def plot_winning_hand(self, img: NDArray) -> Image.Image:
        if self.winning_hand is None or self.best_model is None:
            raise ValueError("No winning hand found.")

        centers = self.winning_hand.centers.copy()
        centers[:, 0] *= img.shape[1]
        centers[:, 1] *= img.shape[0]

        cv2.polylines(
            img, [centers.astype(np.int32).reshape(-1, 1, 2)], False, (255, 0, 0), 3
        )

        return Image.fromarray(img)


class LinearRegressor:
    def __init__(self, X: NDArray) -> None:
        self.m, self.c = np.polyfit(X[:, 0], X[:, 1], 1)

    def predict(self, X: NDArray) -> NDArray:
        return X[:, 0] * self.m + self.c


def abs_error(y_true: NDArray, y_pred: NDArray) -> NDArray:
    return np.abs(y_true - y_pred)


def mean_squared_error(y_true: NDArray, y_pred: NDArray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


def RANSAC(
    X: NDArray,
    metric: Callable[[NDArray, NDArray], float],
    n_iter: int = 10,
    threshold: float = 1e-2,
    min_inliers: int = MIN_NUM_WINNING_TILES,
) -> Tuple[Optional[LinearRegressor], Optional[NDArray]]:
    """RANSAC algorithm

    Args:
        metric (Callable[[NDArray, NDArray], float]): metric function to calculate the performance of the model.
        X (NDArray): 2D array of shape (n_samples, 2) representing the x and y coordinates of the center point of detections.
        n_iter (int, optional): number of iterations. Defaults to 10.
        threshold (float, optional): threshold to determine if points are inliers. Defaults to 1e-2.
        min_inliers (int, optional): number of close points required to assert model fits well. Defaults to MIN_NUM_WINNING_TILES.

    Returns:
        Tuple[Optional[LinearRegressor], Optional[NDArray]]: best model and inliers indices
    """
    if X.shape[0] < min_inliers:
        # not enough inliers
        return None, None

    rng = np.random.default_rng()
    best_score = np.inf
    best_model = None

    for _ in range(n_iter):
        # sample random points from X
        X_sample = rng.choice(X, size=4)

        # fit a linear model to the sampled points
        temp_model = LinearRegressor(X_sample)
        y_predict = temp_model.predict(X)
        err = abs_error(y_predict, X[:, 1])
        inliers_indices = err < threshold

        if np.count_nonzero(inliers_indices) >= min_inliers:
            # fit a model using inliers only
            X_inliers = X[inliers_indices]
            new_model = LinearRegressor(X_inliers)

            # TODO check if distance between centers are reasonable
            score = metric(X_inliers[:, 1], new_model.predict(X_inliers))
            if score < best_score:
                best_score = score
                best_model = new_model

    if best_model is None:
        return None, None

    y_predict = best_model.predict(X)
    inliers_indices = abs_error(y_predict, X[:, 1]) < threshold
    return (best_model, inliers_indices)
