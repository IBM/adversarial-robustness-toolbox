# MIT License
#
# Copyright (C) IBM Corporation 2020
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
This module implements the MP3 compression defence `Mp3Compression`.

| Paper link: https://arxiv.org/abs/1801.01944

| Please keep in mind the limitations of defences. For details on how to evaluate classifier security in general,
    see https://arxiv.org/abs/1902.06705  .
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from io import BytesIO

import numpy as np

from art.defences.preprocessor.preprocessor import Preprocessor
from art.utils import Deprecated, deprecated_keyword_arg

logger = logging.getLogger(__name__)


class Mp3Compression(Preprocessor):
    """
    Implement the MP3 compression defense approach.
    """

    params = ["channel_index", "channels_first", "sample_rate"]

    @deprecated_keyword_arg("channel_index", end_version="1.5.0", replaced_by="channels_first")
    def __init__(
        self, sample_rate, channel_index=Deprecated, channels_first=False, apply_fit=True, apply_predict=False
    ):
        """
        Create an instance of MP3 compression.

        :param channel_index: Index of the axis containing the audio channels.
        :type channel_index: `int`
        :param channels_first: Set channels first or last.
        :type channels_first: `bool`
        :param sample_rate: Specifies the sampling rate of sample.
        :type sample_rate: `int`
        :param apply_fit: True if applied during fitting/training.
        :type apply_fit: `bool`
        :param apply_predict: True if applied during predicting.
        :type apply_predict: `bool`
        """
        # Remove in 1.5.0
        if channel_index == 3:
            channels_first = False
        elif channel_index == 1:
            channels_first = True
        elif channel_index is not Deprecated:
            raise ValueError("Not a proper channel_index. Use channels_first.")

        super().__init__()
        self._is_fitted = True
        self._apply_fit = apply_fit
        self._apply_predict = apply_predict
        self.set_params(channel_index=channel_index, channels_first=channels_first, sample_rate=sample_rate)

    @property
    def apply_fit(self):
        return self._apply_fit

    @property
    def apply_predict(self):
        return self._apply_predict

    def __call__(self, x, y=None):
        """
        Apply MP3 compression to sample `x`.

        :param x: Sample to compress with shape `(batch_size, length, channel)`. `x` values are
        recommended to be of type `np.int16`.
        :type x: `np.ndarray`
        :param y: Labels of the sample `x`. This function does not affect them in any way.
        :type y: `np.ndarray`
        :return: Compressed sample.
        :rtype: `np.ndarray`
        """

        def wav_to_mp3(x, sample_rate):
            """
            Apply MP3 compression to audio input of shape (samples, channel).
            """
            # WARNING: Writing and reading MP3 from byte stream causes pydub to extend the original
            # length. Writing and reading MP3 from local file system works without problems. It is
            # easy to move from using BytesIO to local read/writes with the following:
            # import os
            # from art.config import ART_DATA_PATH
            # tmp_wav = os.path.join(ART_DATA_PATH, "tmp.wav")
            # tmp_mp3 = os.path.join(ART_DATA_PATH, "tmp.mp3")
            from pydub import AudioSegment
            from scipy.io.wavfile import write

            tmp_wav, tmp_mp3 = BytesIO(), BytesIO()
            write(tmp_wav, sample_rate, x)
            AudioSegment.from_wav(tmp_wav).export(tmp_mp3)
            audio_segment = AudioSegment.from_mp3(tmp_mp3)
            tmp_wav.close()
            tmp_mp3.close()
            x_mp3 = np.array(audio_segment.get_array_of_samples()).reshape((-1, audio_segment.channels))
            # WARNING: Due to above problem, we need to manually resize x_mp3 to original length.
            x_mp3 = x_mp3[: x.shape[0]]
            return x_mp3

        if x.ndim != 3:
            raise ValueError("Mp3 compression can only be applied to temporal data across at least one channel.")

        if self.channels_first:
            x = np.swapaxes(x, 1, 2)

        # apply mp3 compression per audio item
        x_mp3 = x.copy()
        for i, x_i in enumerate(x):
            x_mp3[i] = wav_to_mp3(x_i, self.sample_rate)

        if self.channels_first:
            x_mp3 = np.swapaxes(x_mp3, 1, 2)
        return x_mp3

    def estimate_gradient(self, x, grad):
        return grad

    def fit(self, x, y=None, **kwargs):
        """
        No parameters to learn for this method; do nothing.
        """
        pass

    def set_params(self, **kwargs):
        """
        Take in a dictionary of parameters and applies defence-specific checks before saving them as attributes.
        """
        super().set_params(**kwargs)

        if not (isinstance(self.sample_rate, (int, np.int)) and self.sample_rate > 0):
            raise ValueError("Sample rate be must a positive integer.")
        return True
