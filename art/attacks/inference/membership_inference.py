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
This module implements membership inference attacks.

"""

from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data.dataset import Dataset
from torch.utils.data import DataLoader

from art.attacks import InferenceAttack
from art.estimators.estimator import BaseEstimator, NeuralNetworkMixin
from art.estimators.classification.classifier import ClassifierMixin, Classifier
from art.utils import check_and_transform_label_format
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

logger = logging.getLogger(__name__)

use_cuda = torch.cuda.is_available()


def to_cuda(x):
    if use_cuda:
        x = x.cuda()
    return x


class AttackDataset(Dataset):
    def __init__(self, x1, x2, y=None):
        self.x1 = torch.from_numpy(x1.astype(np.float64)).type(torch.FloatTensor)
        self.x2 = torch.from_numpy(x2.astype(np.int32)).type(torch.FloatTensor)

        if y is not None:
            self.y = torch.from_numpy(y.astype(np.int8)).type(torch.FloatTensor)
        else:
            self.y = torch.zeros(x1.shape[0])

    def __len__(self):
        return len(self.x1)

    def __getitem__(self, idx):
        if idx >= len(self.x1):
            raise IndexError("Invalid Index")

        return self.x1[idx], self.x2[idx], self.y[idx]


class MembershipInferenceAttackModel(nn.Module):

    def __init__(self, num_classes, num_features=None):

        self.num_classes = num_classes
        if num_features:
            self.num_features = num_features
        else:
            self.num_features = num_classes

        super(MembershipInferenceAttackModel, self).__init__()

        self.features = nn.Sequential(
            nn.Linear(self.num_features, 512),
            nn.ReLU(),
            nn.Linear(512, 100),
            nn.ReLU(),
            nn.Linear(100, 64),
            nn.ReLU(),
        )

        self.labels = nn.Sequential(
            nn.Linear(self.num_classes, 256),
            nn.ReLU(),
            nn.Linear(256, 64),
            nn.ReLU(),
        )

        self.combine = nn.Sequential(
            nn.Linear(64 * 2, 1),
        )

        self.output = nn.Sigmoid()

    def forward(self, x1, l):
        out_x1 = self.features(x1)
        out_l = self.labels(l)
        is_member = self.combine(torch.cat((out_x1, out_l), 1))
        return self.output(is_member)


class MembershipInferenceBlackBoxRuleBased(InferenceAttack):
    """
        Implementation of a simple, rule-based black-box membership inference attack.

        This implementation uses the simple rule: if the model's prediction for a sample is correct, then it is a
        member. Otherwise, it is not a member.
    """
    _estimator_requirements = [BaseEstimator]

    def __init__(self, classifier: Classifier):
        """
        Create a MembershipInferenceBlackBoxRuleBased attack instance.

        :param classifier: Target classifier.
        """
        super(MembershipInferenceBlackBoxRuleBased, self).__init__(estimator=classifier)


    def infer(self, x: np.ndarray, y: np.ndarray, **kwargs) -> np.ndarray:
        """
        Infer membership in the training set of the target estimator.

        :param x: Input records to attack.
        :param y: True labels for `x`.
        :return: An array holding the inferred membership status, 1 indicates a member and 0 indicates non-member.
        """

        if self.estimator.input_shape[0] != x.shape[1]:
            raise ValueError("Shape of x does not match input_shape of classifier")

        y = check_and_transform_label_format(y, len(np.unique(y)), return_one_hot=True)
        y = np.array([np.argmax(arr) for arr in y]).reshape(-1, 1)
        if y.shape[0] != x.shape[0]:
            raise ValueError("Number of rows in x and y do not match")

        # get model's predictions for x
        predictions = np.array([np.argmax(arr) for arr in self.estimator.predict(x)]).reshape(-1, 1)
        return [1 if p == y[index] else 0 for index, p in enumerate(predictions)]


class MembershipInferenceBlackBox(InferenceAttack):
    """
        Implementation of a learned black-box membership inference attack.

        This implementation can use as input to the learning process probabilities/logits or losses,
        depending on the type of model and provided configuration.
    """
    _estimator_requirements = [BaseEstimator]

    def __init__(self, classifier: Classifier, input_type: Optional[str] = 'prediction',
                 attack_model_type: Optional[str] = 'nn', attack_model: Optional[Classifier] = None):
        """
        Create a MembershipInferenceBlackBox attack instance.

        :param classifier: Target classifier.
        :param attack_model_type: the type of default attack model to train, optional. Should be one of `nn` (for neural
                                  network, default), `rf` (for random forest) or `gb` (gradient boosting). If
                                  `attack_model` is supplied, this option will be ignored.
        :param input_type: the type of input to train the attack on. Can be one of: 'prediction' or 'loss'. Default is
                           `prediction`. Predictions can be either probabilities or logits, depending on the return type
                           of the model.
        :param attack_model: The attack model to train, optional. If none is provided, a default model will be created.
        """
        super(MembershipInferenceBlackBox, self).__init__(estimator=classifier)

        if input_type not in ['prediction', 'loss']:
            raise ValueError("Illegal value for parameter `input_type`.")

        self.input_type = input_type

        if attack_model:
            if ClassifierMixin not in type(attack_model).__mro__:
                raise TypeError("Attack model must be of type Classifier.")
            self.attack_model = attack_model
            self.default_model = False
            self.attack_model_type = None
        else:
            self.default_model = True
            self.attack_model_type = attack_model_type
            if attack_model_type == 'nn':
                if input_type == 'prediction':
                    self.attack_model = MembershipInferenceAttackModel(classifier.nb_classes)
                else:
                    self.attack_model = MembershipInferenceAttackModel(classifier.nb_classes, 1)
                self.epochs = 100
                self.bs = 100
                self.lr = 0.0001
            elif attack_model_type == 'rf':
                self.attack_model = RandomForestClassifier()
            elif attack_model_type == 'gb':
                self.attack_model = GradientBoostingClassifier()
            else:
                raise ValueError("Illegal value for parameter `attack_model_type`.")

    def fit(self, x: np.ndarray, y: np.ndarray, test_x: np.ndarray, test_y: np.ndarray, **kwargs) -> np.ndarray:
        """
        Infer membership in the training set of the target estimator.

        :param x: Records that were used in training the target model.
        :param y: True labels for `x`.
        :param test_x: Records that were not used in training the target model.
        :param test_y: True labels for `test_x`.
        :return: An array holding the inferred membership status, 1 indicates a member and 0 indicates non-member.
        """

        if self.estimator.input_shape[0] != x.shape[1]:
            raise ValueError("Shape of x does not match input_shape of classifier")
        if self.estimator.input_shape[0] != test_x.shape[1]:
            raise ValueError("Shape of test_x does not match input_shape of classifier")

        y = check_and_transform_label_format(y, len(np.unique(y)), return_one_hot=True)
        test_y = check_and_transform_label_format(test_y, len(np.unique(test_y)), return_one_hot=True)

        if y.shape[0] != x.shape[0]:
            raise ValueError("Number of rows in x and y do not match")
        if test_y.shape[0] != test_x.shape[0]:
            raise ValueError("Number of rows in test_x and test_y do not match")

        # Create attack dataset
        # uses final probabilities/logits
        if self.input_type == 'prediction':
            # members
            features = self.estimator.predict(x).astype(np.float32)
            # non-members
            test_features = self.estimator.predict(test_x).astype(np.float32)
        # only for models with loss
        elif self.input_type == 'loss':
            if NeuralNetworkMixin not in type(self.estimator).__mro__:
                raise TypeError("loss input_type can only be used with neural networks")
            # members
            features = self.estimator.loss(x, y).astype(np.float32).reshape(-1, 1)
            # non-members
            test_features = self.estimator.loss(test_x, test_y).astype(np.float32).reshape(-1, 1)
        else:
            raise ValueError("Illegal value for parameter `input_type`.")

        # members
        labels = np.ones(x.shape[0])
        # non-members
        test_labels = np.zeros(test_x.shape[0])

        x1 = np.concatenate((features, test_features))
        x2 = np.concatenate((y, test_y))
        y_new = np.concatenate((labels, test_labels))

        if self.default_model and self.attack_model_type == 'nn':
            loss_fn = nn.BCELoss()
            optimizer = optim.Adam(self.attack_model.parameters(), lr=self.lr)

            attack_train_set = AttackDataset(x1=x1, x2=x2, y=y_new)
            train_loader = DataLoader(attack_train_set, batch_size=self.bs, shuffle=True, num_workers=0)

            self.attack_model = to_cuda(self.attack_model)
            self.attack_model.train()

            for epoch in range(self.epochs):
                for (input1, input2, targets) in train_loader:
                    input1, input2, targets = to_cuda(input1), to_cuda(input2), to_cuda(targets)
                    inputs1, input2 = torch.autograd.Variable(input1), torch.autograd.Variable(input2)
                    targets = torch.autograd.Variable(targets)

                    optimizer.zero_grad()
                    outputs = self.attack_model(input1, input2)
                    loss = loss_fn(outputs, targets.unsqueeze(1))

                    loss.backward()
                    optimizer.step()
        else:
            if self.attack_model_type == 'gb':
                y_ready = check_and_transform_label_format(y_new, len(np.unique(y_new)), return_one_hot=False)
            else:
                y_ready = check_and_transform_label_format(y_new, len(np.unique(y_new)), return_one_hot=True)
            self.attack_model.fit(np.c_[x1, x2], y_ready)

    def infer(self, x: np.ndarray, y: np.ndarray, **kwargs) -> np.ndarray:
        """
        Infer membership in the training set of the target estimator.

        :param x: Input records to attack.
        :param y: True labels for `x`.
        :return: An array holding the inferred membership status, 1 indicates a member and 0 indicates non-member.
        """
        if self.estimator.input_shape[0] != x.shape[1]:
            raise ValueError("Shape of x does not match input_shape of classifier")

        y = check_and_transform_label_format(y, len(np.unique(y)), return_one_hot=True)

        if y.shape[0] != x.shape[0]:
            raise ValueError("Number of rows in x and y do not match")

        if self.input_type == 'prediction':
            features = self.estimator.predict(x).astype(np.float32)
        elif self.input_type == 'loss':
            features = self.estimator.loss(x, y).astype(np.float32).reshape(-1, 1)

        if self.default_model and self.attack_model_type == 'nn':
            self.attack_model.eval()
            inferred = None
            test_set = AttackDataset(x1=features, x2=y)
            test_loader = DataLoader(test_set, batch_size=self.bs, shuffle=True, num_workers=0)
            for input1, input2, targets in test_loader:
                outputs = self.attack_model(input1, input2)
                predicted = torch.round(outputs)
                if inferred is None:
                    inferred = predicted.detach().numpy()
                else:
                    inferred = np.vstack((inferred, predicted.detach().numpy()))
        else:
            inferred = np.array([np.argmax(arr) for arr in self.attack_model.predict(np.c_[features, y])])
        return inferred


class MembershipInferenceWhiteBoxNeuralNetwork(InferenceAttack):
    """
        Implementation of a learned white-box membership inference attack.

        This implementation can use as input to the learning process activations and/or gradients of one or more layers,
        depending on the provided configuration.
    """
    def __init__(self, classifier: Classifier):
        raise NotImplementedError

    def infer(self, x: np.ndarray, y: Optional[np.ndarray] = None, **kwargs) -> np.ndarray:
        """
        Infer sensitive properties (attributes, membership training records) from the targeted estimator. This method
        should be overridden by all concrete inference attack implementations.

        :param x: An array with reference inputs to be used in the attack.
        :param y: Labels for `x`. This parameter is only used by some of the attacks.
        :return: An array holding the inferred properties.
        """
        raise NotImplementedError
        # if NeuralNetworkMixin in type(self.estimator).__mro__:
        #     activations = self.estimator.get_activations(x, self.estimator.layer_names[-1], batch_size=self.bs)