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
This module tests the Pixel Attack.
The Pixel Attack is a generalisation of One Pixel Attack.

| One Pixel Attack Paper link:
    https://ieeexplore.ieee.org/abstract/document/8601309/citations#citations
    (arXiv link: https://arxiv.org/pdf/1710.08864.pdf)
| Pixel Attack Paper link:
    https://arxiv.org/abs/1906.06026
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

import numpy as np
import pytest

from art.attacks.evasion.pixel_threshold import PixelAttack
from art.estimators.estimator import BaseEstimator, NeuralNetworkMixin
from art.estimators.classification.classifier import ClassifierMixin
from art.utils import get_labels_np_array

from tests.attacks.utils import backend_test_classifier_type_check_fail
from tests.utils import ARTTestException

logger = logging.getLogger(__name__)


@pytest.fixture()
def fix_get_mnist_subset(get_mnist_dataset):
    (x_train_mnist, y_train_mnist), (x_test_mnist, y_test_mnist) = get_mnist_dataset
    n_train = 100
    n_test = 2
    yield x_train_mnist[:n_train], y_train_mnist[:n_train], x_test_mnist[:n_test], y_test_mnist[:n_test]


@pytest.mark.skipMlFramework("scikitlearn", "tensorflow2v1")
@pytest.mark.parametrize("targeted", [True, False])
def test_image(fix_get_mnist_subset, image_dl_estimator, targeted, art_warning):
    try:
        (x_train_mnist, y_train_mnist, x_test_mnist, y_test_mnist) = fix_get_mnist_subset

        estimator, _ = image_dl_estimator()

        x_test_original = x_test_mnist.copy()

        if targeted:
            # Generate random target classes
            class_y_test = np.argmax(y_test_mnist, axis=1)
            nb_classes = np.unique(class_y_test).shape[0]

            targets = np.random.randint(nb_classes, size=x_test_mnist.shape[0])
            for i in range(x_test_mnist.shape[0]):
                if class_y_test[i] == targets[i]:
                    targets[i] -= 1
        else:
            targets = y_test_mnist

        for es in [0, 1]:
            df = PixelAttack(estimator, th=64, es=es, targeted=targeted)
            x_test_adv = df.generate(x_test_original, targets, max_iter=1)

            np.testing.assert_raises(AssertionError, np.testing.assert_array_equal, x_test_mnist, x_test_adv)
            np.testing.assert_raises(AssertionError, np.testing.assert_array_equal, 0.0, x_test_adv)

            y_pred = get_labels_np_array(estimator.predict(x_test_adv))
            np.testing.assert_raises(AssertionError, np.testing.assert_array_equal, y_test_mnist, y_pred)

            accuracy = np.sum(np.argmax(y_pred, axis=1) == np.argmax(y_test_mnist, axis=1)) / x_test_mnist.shape[0]
            logger.info("Accuracy on adversarial examples: %.2f%%", (accuracy * 100))

        # Check that x_test has not been modified by attack and classifier
        np.testing.assert_array_almost_equal(float(np.max(np.abs(x_test_original - x_test_mnist))), 0, decimal=5)
    except ARTTestException as e:
        art_warning(e)


def test_classifier_type_check_fail(art_warning):
    try:
        backend_test_classifier_type_check_fail(PixelAttack, [BaseEstimator, NeuralNetworkMixin, ClassifierMixin])
    except ARTTestException as e:
        art_warning(e)
