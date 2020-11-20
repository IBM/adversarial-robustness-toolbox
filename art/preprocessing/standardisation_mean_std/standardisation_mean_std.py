# MIT License
#
# Copyright (C) The Adversarial Robustness Toolbox (ART) Authors 2020
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
This module implements the standardisation with mean and standard deviation.
"""
import logging
from typing import Optional, Tuple

import numpy as np

from art.config import ART_NUMPY_DTYPE
from art.defences.preprocessor.preprocessor import Preprocessor


logger = logging.getLogger(__name__)


class StandardisationMeanStd(Preprocessor):
    """
    Implement the standardisation with mean and standard deviation.
    """

    params = ["mean", "std", "apply_fit", "apply_predict"]

    def __init__(
        self, mean: float = 0.0, std: float = 1.0, apply_fit: bool = True, apply_predict: bool = True,
    ):
        """
        Create an instance of StandardisationMeanStd.

        :param mean: Mean.
        :param std: Standard Deviation.
        """
        super().__init__()
        self._is_fitted = True
        self._apply_fit = apply_fit
        self._apply_predict = apply_predict
        self.mean = mean
        self.std = std
        self._check_params()

    @property
    def apply_fit(self) -> bool:
        return self._apply_fit

    @property
    def apply_predict(self) -> bool:
        return self._apply_predict

    def __call__(self, x: np.ndarray, y: Optional[np.ndarray] = None,) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Apply StandardisationMeanStd inputs `x`.

        :param x: Input samples to standardise of shapes `NCHW`, `NHWC`, `NCFHW` or `NFHWC`.
        :param y: Label data, will not be affected by this preprocessing.
        :return: Standardise input samples and unmodified labels.
        """
        if x.dtype in [np.uint8, np.uint16, np.uint32, np.uint64]:
            raise TypeError(
                "The data type of input data `x` is {} and cannot represent negative values. Consider "
                "changing the data type of the input data `x` to a type that supports negative values e.g. "
                "np.float32.".format(x.dtype)
            )

        mean = np.asarray(self.mean, dtype=ART_NUMPY_DTYPE)
        std = np.asarray(self.std, dtype=ART_NUMPY_DTYPE)

        x_norm = x - mean
        x_norm = x_norm / std
        x_norm = x_norm.astype(ART_NUMPY_DTYPE)

        return x_norm, y

    def estimate_gradient(self, x: np.ndarray, gradient: np.ndarray) -> np.ndarray:

        std = np.asarray(self.std, dtype=ART_NUMPY_DTYPE)
        gradient_back = gradient / std

        return gradient_back

    def fit(self, x: np.ndarray, y: Optional[np.ndarray] = None, **kwargs) -> None:
        """
        No parameters to learn for this method; do nothing.
        """
        pass

    def _check_params(self) -> None:
        pass

    def __repr__(self):
        return "StandardisationMeanStd(mean={}, std={}, apply_fit={}, apply_predict={})".format(
            self.mean, self.std, self.apply_fit, self.apply_predict
        )