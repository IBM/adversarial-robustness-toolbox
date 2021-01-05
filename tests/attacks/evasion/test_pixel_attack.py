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

from tests.utils import TestBase
from tests.utils import get_image_classifier_tf, get_image_classifier_kr, get_image_classifier_pt
from tests.attacks.utils import backend_test_classifier_type_check_fail

logger = logging.getLogger(__name__)


@pytest.fixture()
def fix_get_mnist_subset(get_mnist_dataset):
    (x_train_mnist, y_train_mnist), (x_test_mnist, y_test_mnist) = get_mnist_dataset
    n_train = 100
    n_test = 2
    yield x_train_mnist[:n_train], y_train_mnist[:n_train], x_test_mnist[:n_test], y_test_mnist[:n_test]


def test_mnist(fix_get_mnist_subset):
    (x_train_mnist, y_train_mnist, x_test_mnist, y_test_mnist) = fix_get_mnist_subset

    estimator, sess = get_image_classifier_tf()

    x_test_original = x_test_mnist.copy()
    targeted = True
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

        # self.assertFalse((x_test_mnist == x_test_adv).all())
        # self.assertFalse((0.0 == x_test_adv).all())

        y_pred = get_labels_np_array(estimator.predict(x_test_adv))
        # self.assertFalse((y_test_mnist == y_pred).all())

        accuracy = np.sum(np.argmax(y_pred, axis=1) == np.argmax(y_test_mnist, axis=1)) / x_test_mnist.shape[0]
        logger.info("Accuracy on adversarial examples: %.2f%%", (accuracy * 100))

    # Check that x_test has not been modified by attack and classifier
    # self.assertAlmostEqual(float(np.max(np.abs(x_test_original - x_test_mnist))), 0.0, delta=0.00001)

# class TestPixelAttack(TestBase):
#     """
#     A unittest class for testing the Pixel Attack.
#
#     This module tests the Pixel Attack.
#     The Pixel Attack is a generalisation of One Pixel Attack.
#
#     | One Pixel Attack Paper link:
#         https://ieeexplore.ieee.org/abstract/document/8601309/citations#citations
#         (arXiv link: https://arxiv.org/pdf/1710.08864.pdf)
#     | Pixel Attack Paper link:
#         https://arxiv.org/abs/1906.06026
#     """
#
#     @classmethod
#     def setUpClass(cls):
#         super().setUpClass()
#
#         cls.n_test = 2
#         cls.x_test_mnist = cls.x_test_mnist[0 : cls.n_test]
#         cls.y_test_mnist = cls.y_test_mnist[0 : cls.n_test]
#
#     def test_6_keras_mnist(self):
#         """
#         Test with the KerasClassifier. (Untargeted Attack)
#         :return:
#         """
#
#         classifier = get_image_classifier_kr()
#         self._test_attack(classifier, self.x_test_mnist, self.y_test_mnist, False)
#
#     def test_2_tensorflow_mnist(self):
#         """
#         Test with the TensorFlowClassifier. (Untargeted Attack)
#         :return:
#         """
#         classifier, sess = get_image_classifier_tf()
#         self._test_attack(classifier, self.x_test_mnist, self.y_test_mnist, False)
#
#     def test_4_pytorch_mnist(self):
#         """
#         Test with the PyTorchClassifier. (Untargeted Attack)
#         :return:
#         """
#         x_test = np.reshape(self.x_test_mnist, (self.x_test_mnist.shape[0], 1, 28, 28)).astype(np.float32)
#         classifier = get_image_classifier_pt()
#         self._test_attack(classifier, x_test, self.y_test_mnist, False)
#
#     def test_7_keras_mnist_targeted(self):
#         """
#         Test with the KerasClassifier. (Targeted Attack)
#         :return:
#         """
#         classifier = get_image_classifier_kr()
#         self._test_attack(classifier, self.x_test_mnist, self.y_test_mnist, True)
#
#     def test_3_tensorflow_mnist_targeted(self):
#         """
#         Test with the TensorFlowClassifier. (Targeted Attack)
#         :return:
#         """
#         classifier, sess = get_image_classifier_tf()
#         self._test_attack(classifier, self.x_test_mnist, self.y_test_mnist, True)
#
#     def test_5_pytorch_mnist_targeted(self):
#         """
#         Test with the PyTorchClassifier. (Targeted Attack)
#         :return:
#         """
#         x_test = np.reshape(self.x_test_mnist, (self.x_test_mnist.shape[0], 1, 28, 28)).astype(np.float32)
#         classifier = get_image_classifier_pt()
#         self._test_attack(classifier, x_test, self.y_test_mnist, True)
#

#
#     def test_1_classifier_type_check_fail(self):
#         backend_test_classifier_type_check_fail(PixelAttack, [BaseEstimator, NeuralNetworkMixin, ClassifierMixin])
#
