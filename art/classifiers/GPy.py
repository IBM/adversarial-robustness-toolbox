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
from __future__ import absolute_import, division, print_function, unicode_literals

import logging

import numpy as np

from art.classifiers import Classifier, ClassifierGradients

logger = logging.getLogger(__name__)


class GPyGaussianProcessClassifier(Classifier, ClassifierGradients):
    """
    Wrapper class for GPy Gaussian Process classification models.
    """

    def __init__(self, model=None, clip_values=None, defences=None, preprocessing=(0, 1)):
        """
        Create a `Classifier` instance GPY Gaussian Process classification models.

        :param clip_values: Tuple of the form `(min, max)` representing the minimum and maximum values allowed
               for features.
        :type clip_values: `tuple`
        :param model: GPY Gaussian Process Classification model.
        :type model: `Gpy.models.GPClassification`
        :param defences: Defences to be activated with the classifier.
        :type defences: :class:`.Preprocessor` or `list(Preprocessor)` instances
        :param preprocessing: Tuple of the form `(subtractor, divider)` of floats or `np.ndarray` of values to be
               used for data preprocessing. The first value will be subtracted from the input. The input will then
               be divided by the second one.
        :type preprocessing: `tuple`
        """
        from GPy.models import GPClassification as GPC

        if not isinstance(model, GPC):
            raise TypeError(
                'Model must be of type GPy.models.GPClassification')
        super(GPyGaussianProcessClassifier, self).__init__(clip_values=clip_values,
                                                           defences=defences,
                                                           preprocessing=preprocessing)
        self._nb_classes = 2  # always binary
        self.model = model

    def class_gradient(self, x, label=None, eps=0.0001):
        """
        Compute per-class derivatives w.r.t. `x`.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :param label: Index of a specific per-class derivative. If an integer is provided, the gradient of that class
                      output is computed for all samples. If multiple values as provided, the first dimension should
                      match the batch size of `x`, and each value will be used as target for its corresponding sample in
                      `x`. If `None`, then gradients for all classes will be computed for each sample.
        :type label: `int` or `list`
        :return: Array of gradients of input features w.r.t. each class in the form
                 `(batch_size, nb_classes, input_shape)` when computing for all classes, otherwise shape becomes
                 `(batch_size, 1, input_shape)` when `label` parameter is specified.
        :rtype: `np.ndarray`
        """
        grads = np.zeros((np.shape(x)[0], 2, np.shape(x)[1]))
        for i in range(np.shape(x)[0]):
            # get gradient for the two classes GPC can maximally have
            for c in range(2):
                ind = self.predict(x[i].reshape(1, -1))[0, c]
                sur = self.predict(np.repeat(x[i].reshape(1, -1),
                                             np.shape(x)[1], 0) + eps * np.eye(np.shape(x)[1]))[:, c]
                grads[i, c] = ((sur - ind) * eps).reshape(1, -1)

        if label is not None:
            return grads[:, label, :].reshape(np.shape(x)[0], 1, np.shape(x)[1])

        return grads

    def get_activations(self, x, layer, batch_size):
        raise NotImplementedError

    def loss_gradient(self, x, y, **kwargs):
        """
        Compute the gradient of the loss function w.r.t. `x`.

        :param x: Sample input with shape as expected by the model.
        :type x: `np.ndarray`
        :param y: Correct labels, one-vs-rest encoding.
        :type y: `np.ndarray`
        :return: Array of gradients of the same shape as `x`.
        :rtype: `np.ndarray`
        """
        eps = 0.00001
        grads = np.zeros(np.shape(x))
        for i in range(np.shape(x)[0]):
            # 1.0 - to mimic loss, [0,np.argmax] to get right class
            ind = 1.0 - self.predict(x[i].reshape(1, -1))[0, np.argmax(y[i])]
            sur = 1.0 - self.predict(np.repeat(x[i].reshape(1, -1), np.shape(x)[1], 0)
                                     + eps * np.eye(np.shape(x)[1]))[:, np.argmax(y[i])]
            grads[i] = ((sur - ind) * eps).reshape(1, -1)
        return grads

    def predict(self, x, logits=False):
        """
        Perform prediction for a batch of inputs.

        :param x: Test set.
        :type x: `np.ndarray`
        :param logits: `True` if the prediction should be done without squashing function.
        :type logits: `bool`
        :return: Array of predictions of shape `(nb_inputs, self.nb_classes)`.
        :rtype: `np.ndarray`
        """
        out = np.zeros((np.shape(x)[0], 2))
        if logits:  # output the non-squashed version
            out[:, 0] = self.model.predict_noiseless(x)[0].reshape(-1)
            out[:, 1] = -1.0 * out[:, 0]
            return out
        # output normal prediction, scale up to two values
        out[:, 0] = self.model.predict(x)[0].reshape(-1)
        out[:, 1] = 1.0 - out[:, 0]
        return out

    def predict_uncertainty(self, x):
        """
        Perform uncertainty prediction for a batch of inputs.

        :param x: Test set.
        :type x: `np.ndarray`
        :return: Array of uncertainty predictions of shape `(nb_inputs)`.
        :rtype: `np.ndarray`
        """
        return self.model.predict_noiseless(x)[1]

    def fit(self, x, y, **kwargs):
        """
        Fit the classifier on the training set `(x, y)`.

        :param x: Training data. Not used, as given to model in initialized earlier.
        :type x: `np.ndarray`
        :param y: Labels, one-vs-rest encoding. Not used, as given to model in initialized earlier.
        :type y: `np.ndarray`
        :type kwargs: `dict`
        :return: `None`
        """
        raise NotImplementedError

    def save(self, filename, path=None):
        self.model.save_model(filename, save_data=False)
