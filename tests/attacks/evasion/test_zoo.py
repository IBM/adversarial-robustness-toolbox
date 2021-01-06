# MIT License
#
# Copyright (C) The Adversarial Robustness Toolbox (ART) Authors 2018
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
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

import keras.backend as k
import numpy as np
import pytest

from art.attacks.evasion.zoo import ZooAttack
from art.estimators.estimator import BaseEstimator
from art.estimators.classification.classifier import ClassifierMixin
from art.utils import random_targets

from tests.utils import TestBase, get_image_classifier_kr, get_image_classifier_pt
from tests.utils import get_image_classifier_tf, master_seed
from tests.attacks.utils import backend_test_classifier_type_check_fail

logger = logging.getLogger(__name__)


@pytest.fixture()
def fix_get_mnist_subset(get_mnist_dataset):
    (x_train_mnist, y_train_mnist), (x_test_mnist, y_test_mnist) = get_mnist_dataset
    n_train = 1
    n_test = 1
    yield x_train_mnist[:n_train], y_train_mnist[:n_train], x_test_mnist[:n_test], y_test_mnist[:n_test]


def assert_less_or_equal(x, y):
    '''
    temporary replacement for the missing numpy (replacing unitTest.assertGreaterEqual(x,y)
    :return:
    '''
    try:
        np.testing.assert_array_equal(x, y)
    except Exception as e:
        np.testing.assert_array_less(x, y)


def test_failure_attack(fix_get_mnist_subset, image_dl_estimator):
    """
    Test the corner case when attack fails.
    :return:
    """
    (x_train_mnist, y_train_mnist, x_test_mnist, y_test_mnist) = fix_get_mnist_subset

    x_test_original = x_test_mnist.copy()

    # Build TensorFlowClassifier
    # tfc, sess = get_image_classifier_tf()
    estimator, _ = image_dl_estimator()

    # Failure attack
    zoo = ZooAttack(classifier=estimator, max_iter=0, binary_search_steps=0, learning_rate=0)
    x_test_mnist_adv = zoo.generate(x_test_mnist)

    assert_less_or_equal(np.amax(x_test_mnist_adv), 1.0)
    assert_less_or_equal(0.0, np.amin(x_test_mnist_adv))

    np.testing.assert_almost_equal(x_test_mnist, x_test_mnist_adv, 3)

    # Check that x_test has not been modified by attack and classifier
    np.testing.assert_array_almost_equal(float(np.max(np.abs(x_test_original - x_test_mnist))), 0, decimal=5)


def test_classifier_type_check_fail():
    backend_test_classifier_type_check_fail(ZooAttack, [BaseEstimator, ClassifierMixin])

# class TestZooAttack(TestBase):
#     """
#     A unittest class for testing the ZOO attack.
#     """

#

#
#     def test_3_tensorflow_mnist(self):
#         """
#         First test with the TensorFlowClassifier.
#         :return:
#         """
#         x_test_original = self.x_test_mnist.copy()
#
#         # Build TensorFlowClassifier
#         tfc, sess = get_image_classifier_tf()
#
#         # Targeted attack
#         zoo = ZooAttack(classifier=tfc, targeted=True, max_iter=30, binary_search_steps=8, batch_size=128)
#         params = {"y": random_targets(self.y_test_mnist, tfc.nb_classes)}
#         x_test_mnist_adv = zoo.generate(self.x_test_mnist, **params)
#         self.assertFalse((self.x_test_mnist == x_test_mnist_adv).all())
#         self.assertLessEqual(np.amax(x_test_mnist_adv), 1.0)
#         self.assertGreaterEqual(np.amin(x_test_mnist_adv), 0.0)
#         target = np.argmax(params["y"], axis=1)
#         y_pred_adv = np.argmax(tfc.predict(x_test_mnist_adv), axis=1)
#         logger.debug("ZOO target: %s", target)
#         logger.debug("ZOO actual: %s", y_pred_adv)
#         logger.info("ZOO success rate on MNIST: %.2f", (sum(target == y_pred_adv) / float(len(target))))
#
#         # Untargeted attack
#         zoo = ZooAttack(classifier=tfc, targeted=False, max_iter=10, binary_search_steps=3)
#         x_test_mnist_adv = zoo.generate(self.x_test_mnist)
#         # self.assertFalse((x_test == x_test_adv).all())
#         self.assertLessEqual(np.amax(x_test_mnist_adv), 1.0)
#         self.assertGreaterEqual(np.amin(x_test_mnist_adv), 0.0)
#         y_pred = np.argmax(tfc.predict(self.x_test_mnist), axis=1)
#         y_pred_adv = np.argmax(tfc.predict(x_test_mnist_adv), axis=1)
#         logger.debug("ZOO actual: %s", y_pred_adv)
#         logger.info("ZOO success rate on MNIST: %.2f", (sum(y_pred != y_pred_adv) / float(len(y_pred))))
#
#         # Check that x_test has not been modified by attack and classifier
#         self.assertAlmostEqual(float(np.max(np.abs(x_test_original - self.x_test_mnist))), 0.0, delta=0.00001)
#
#         # Clean-up session
#         if sess is not None:
#             sess.close()
#
#     def test_5_keras_mnist(self):
#         """
#         Second test with the KerasClassifier.
#         :return:
#         """
#         x_test_original = self.x_test_mnist.copy()
#
#         # Build KerasClassifier
#         krc = get_image_classifier_kr()
#
#         # Targeted attack
#         # zoo = ZooAttack(classifier=krc, targeted=True, batch_size=5)
#         # params = {'y': random_targets(self.y_test, krc.nb_classes)}
#         # x_test_adv = zoo.generate(self.x_test, **params)
#         #
#         # self.assertFalse((self.x_test == x_test_adv).all())
#         # self.assertLessEqual(np.amax(x_test_adv), 1.0)
#         # self.assertGreaterEqual(np.amin(x_test_adv), 0.0)
#         # target = np.argmax(params['y'], axis=1)
#         # y_pred_adv = np.argmax(krc.predict(x_test_adv), axis=1)
#         # logger.debug('ZOO target: %s', target)
#         # logger.debug('ZOO actual: %s', y_pred_adv)
#         # logger.info('ZOO success rate on MNIST: %.2f', (sum(target == y_pred_adv) / float(len(target))))
#
#         # Untargeted attack
#         # zoo = ZooAttack(classifier=krc, targeted=False, max_iter=20)
#         zoo = ZooAttack(classifier=krc, targeted=False, batch_size=5, max_iter=10, binary_search_steps=3)
#         # x_test_adv = zoo.generate(x_test)
#         params = {"y": random_targets(self.y_test_mnist, krc.nb_classes)}
#         x_test_mnist_adv = zoo.generate(self.x_test_mnist, **params)
#
#         # x_test_adv_true = [0.00000000e+00, 2.50167388e-04, 1.50529508e-04, 4.69674182e-04,
#         #                    0.00000000e+00, 0.00000000e+00, 0.00000000e+00, 0.00000000e+00,
#         #                    1.67321396e-05, 0.00000000e+00, 0.00000000e+00, 0.00000000e+00,
#         #                    0.00000000e+00, 2.08451956e-06, 0.00000000e+00, 0.00000000e+00,
#         #                    2.53360748e-01, 9.60119188e-01, 9.85227525e-01, 2.53600776e-01,
#         #                    0.00000000e+00, 0.00000000e+00, 5.23251540e-04, 0.00000000e+00,
#         #                    0.00000000e+00, 0.00000000e+00, 1.08632184e-05, 0.00000000e+00]
#         #
#         # for i in range(14):
#         #     self.assertAlmostEqual(x_test_adv_true[i], x_test_adv[0, 14, i, 0])
#
#         # self.assertFalse((x_test == x_test_adv).all())
#         self.assertLessEqual(np.amax(x_test_mnist_adv), 1.0)
#         self.assertGreaterEqual(np.amin(x_test_mnist_adv), 0.0)
#         y_pred_adv = np.argmax(krc.predict(x_test_mnist_adv), axis=1)
#         y_pred = np.argmax(krc.predict(self.x_test_mnist), axis=1)
#         logger.debug("ZOO actual: %s", y_pred_adv)
#         logger.info("ZOO success rate on MNIST: %.2f", (sum(y_pred != y_pred_adv) / float(len(y_pred))))
#
#         # Check that x_test has not been modified by attack and classifier
#         self.assertAlmostEqual(float(np.max(np.abs(x_test_original - self.x_test_mnist))), 0.0, delta=0.00001)
#
#         # Clean-up
#         k.clear_session()
#
#     def test_4_pytorch_mnist(self):
#         """
#         Third test with the PyTorchClassifier.
#         :return:
#         """
#         # Build PyTorchClassifier
#         ptc = get_image_classifier_pt()
#
#         # Get MNIST
#         x_test_mnist = np.swapaxes(self.x_test_mnist, 1, 3).astype(np.float32)
#         x_test_original = x_test_mnist.copy()
#
#         # First attack
#         # zoo = ZooAttack(classifier=ptc, targeted=True, max_iter=10, binary_search_steps=10)
#         # params = {'y': random_targets(self.y_test, ptc.nb_classes)}
#         # x_test_adv = zoo.generate(x_test, **params)
#         # self.assertFalse((x_test == x_test_adv).all())
#         # self.assertLessEqual(np.amax(x_test_adv), 1.0)
#         # self.assertGreaterEqual(np.amin(x_test_adv), 0.0)
#         # target = np.argmax(params['y'], axis=1)
#         # y_pred_adv = np.argmax(ptc.predict(x_test_adv), axis=1)
#         # logger.debug('ZOO target: %s', target)
#         # logger.debug('ZOO actual: %s', y_pred_adv)
#         # logger.info('ZOO success rate on MNIST: %.2f', (sum(target != y_pred_adv) / float(len(target))))
#
#         # Second attack
#         zoo = ZooAttack(
#             classifier=ptc,
#             targeted=False,
#             learning_rate=1e-2,
#             max_iter=10,
#             binary_search_steps=3,
#             abort_early=False,
#             use_resize=False,
#             use_importance=False,
#         )
#         x_test_mnist_adv = zoo.generate(x_test_mnist)
#         self.assertLessEqual(np.amax(x_test_mnist_adv), 1.0)
#         self.assertGreaterEqual(np.amin(x_test_mnist_adv), 0.0)
#
#         # print(x_test[0, 0, 14, :])
#         # print(x_test_adv[0, 0, 14, :])
#         # print(np.amax(x_test - x_test_adv))
#         # x_test_adv_expected = []
#
#         # Check that x_test has not been modified by attack and classifier
#         self.assertAlmostEqual(float(np.max(np.abs(x_test_original - x_test_mnist))), 0.0, delta=0.00001)
#
#
