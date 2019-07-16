# MIT License
#
# Copyright (C) IBM Corporation 2018
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
This module implements Randomized Smoothing applied to classifier predictions and Smoothgrad applied to gradients.

Paper link:
    https://arxiv.org/pdf/1902.02918.pdf
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

from art.wrappers.wrapper import ClassifierWrapper

from scipy.stats import norm, binom_test

from statsmodels.stats.proportion import proportion_confint

import numpy as np

logger = logging.getLogger(__name__)


class RandomizedSmoothing(ClassifierWrapper):
    """
    Implementation of Randomized Smoothing applied to classifier predictions and gradients, as introduced
    in Cohen et al. (2019). Paper link: https://arxiv.org/pdf/1902.02918.pdf
    """

    def __init__(self, classifier, sample_size, scale=0.1, alpha=0.001):
        """
        Create a randomized smoothing wrapper.

        :param classifier: The Classifier we want to wrap the functionality for the purpose of smoothing.
        :type classifier: :class:`.Classifier`
        :param sample_size: Number of samples for smoothing
        :type sample_size: `int`
        :param scale: Standard deviation of Gaussian noise added.
        :type scale: `float`
        :param alpha: The failure probability of smoothing
        :type alpha: `float` 
        """
        super(RandomizedSmoothing, self).__init__(classifier)
        self.sample_size = sample_size
        self.scale = scale
        self.alpha = alpha

    def predict(self, x, logits=False, batch_size=128):
        """
        Perform prediction of the given classifier for a batch of inputs, taking an expectation over transformations.

        :param x: Test set.
        :type x: `np.ndarray`
        :param logits: `True` if the prediction should be done at the logits layer.
        :type logits: `bool`
        :param batch_size: Size of batches.
        :type batch_size: `int`
        :return: Array of predictions of shape `(nb_inputs, self.nb_classes)`.
        :rtype: `np.ndarray`
        """
        logger.info('Applying randomized smoothing.')
        prediction = []
        for x_i in x:

            # get class counts
            counts_pred = self._prediction_counts(x_i)
            top = counts_pred.argsort()[::-1]
            count1 = np.max(counts_pred)
            count2 = counts_pred[top[1]]

            # predict or abstain
            smooth_prediction = np.zeros(counts_pred.shape)
            if binom_test(count1, count1 + count2, p=0.5) <= self.alpha:
                smooth_prediction[np.argmax(counts_pred)] = 1
            prediction.append(smooth_prediction)
        return np.array(prediction)

    def loss_gradient(self, x, y):
        """
        Compute the gradient of the given classifier's loss function w.r.t. `x`, taking an expectation
        over transformations.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :param y: Correct labels, one-hot encoded.
        :type y: `np.ndarray`
        :return: Array of gradients of the same shape as `x`.
        :rtype: `np.ndarray`
        """
        logger.info('Applying randomized smoothing.')
        loss_gradient = []
        for idx, x_i in enumerate(x):
            x_new, y_new = self._noisy_samples(x_i, y[idx])
            loss_gradient.append(np.mean(self.classifier.loss_gradient(x_new, y_new), axis=0))
        return loss_gradient

    def class_gradient(self, x, label=None, logits=False):
        """
        Compute per-class derivatives of the given classifier w.r.t. `x`, taking an average over noisy samples.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :param label: Index of a specific per-class derivative. If an integer is provided, the gradient of that class
                      output is computed for all samples. If multiple values as provided, the first dimension should
                      match the batch size of `x`, and each value will be used as target for its corresponding sample in
                      `x`. If `None`, then gradients for all classes will be computed for each sample.
        :type label: `list`
        :param logits: `True` if the prediction should be done at the logits layer.
        :type logits: `bool`
        :return: Array of gradients of input features w.r.t. each class in the form
                 `(batch_size, nb_classes, input_shape)` when computing for all classes, otherwise shape becomes
                 `(batch_size, 1, input_shape)` when `label` parameter is specified.
        :rtype: `np.ndarray`
        """
        logger.info('Apply randomized smoothing.')
        class_gradient = []
        for idx, x_i in enumerate(x):
            if label is None:
                x_new = self._noisy_samples(x_i)
            else:
                x_new, label = self._noisy_samples(x_i, label[idx])
            class_gradient.append(np.mean(self.classifier.class_gradient(x_new, label, logits), axis=0))
        return class_gradient

    def certify(self, x, n):
        """
        Computes certifiable radius around input `x` and returns radius `r` and prediction.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :param n: Number of samples for estimate certifiable radius
        :type n: `int`
        :return: Tuple of length 2 of the selected class and certified radius
        :rtype: `tuple`
        """
        prediction = []
        radius = []
        for x_i in x:

            # get sample prediction for classification
            counts_pred = self._prediction_counts(x_i)
            ca = np.argmax(counts_pred)

            # get sample prediction for certification
            counts_est = self._prediction_counts(x_i, n=n)
            nA = counts_est[ca]

            pABar = self._lower_confidence_bound(nA, n)

            if pABar < 0.5:
                prediction.append(-1)
                radius.append(0.0)
            else:
                prediction.append(ca)
                radius.append(self.scale*norm.ppf(pABar))

        return prediction, radius


    def _noisy_samples(self, x, y=None, n=None):
        """
        Adds Gaussian noise to `x` to generate samples. Optionally augments `y` similarly.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :return: Array of samples of the same shape as `x`.
        :type y: `np.ndarray`
        :return: Array of gradients of the same shape as `x`.
        :rtype: `np.ndarray`
        """
        # set default value to sample_size
        if n is None:
            n = self.sample_size

        # augment x
        x = np.expand_dims(x, axis=0)
        x = np.repeat(x, n, axis=0)
        x = x + np.random.normal(scale=self.scale, size=x.shape)

        # augment y if necessary
        if y is not None:
            y = np.expand_dims(y, axis=0)
            y = np.repeat(y, n, axis=0)
            return x, y
        else:
            return x

    def _prediction_counts(self, x, n=None):
        """
        Makes predictions and then converts probability distribution to counts

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :return: Array of counts with length equal to number of columns of `x`.
        :rtype: `np.ndarray`
        """
        # sample and predict
        x_new = self._noisy_samples(x, n=n)
        predictions = self.classifier.predict(x_new)

         # convert to binary predictions
        idx = np.argmax(predictions, axis=-1)
        pred = np.zeros(predictions.shape)
        pred[np.arange(pred.shape[0]), idx] = 1

        # get class counts
        counts = np.sum(pred, axis=0)

        return counts

    def _lower_confidence_bound(self, nA, n):
        """
        Uses Clopper-Pearson method to return a (1-alpha) lower confidence bound on bernoulli proportion

        :param nA: Number of samples of a specific class.
        :type nA: `int`
        :param n: Number of samples for certification.
        :type n: `int`
        :return: Lower bound on the binomial proportion w.p. (1-alpha) over samples
        :rtype: `float`
        """
        return proportion_confint(nA, n, alpha=2 * self.alpha, method="beta")[0]


