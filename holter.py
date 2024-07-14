from datetime import datetime
import numpy as np

import pydicom as dicom
from scipy.signal import butter, lfilter
import struct

# you would have to generate those models using the openapi specs
# or alternatively you can build the json manually
from models import HolterCreate, Device, Channel


def _get_amplifier(unit: str) -> float:
    if unit == "uV":
        return 1.0
    elif unit == "mV":
        return 1e3
    elif unit == "V":
        return 1e6


def _butter_lowpass_filter(data, highcut, sampfreq, order):
    high = highcut / (sampfreq / 2)
    num, denom = butter(N=order, Wn=high, btype="lowpass")
    return lfilter(num, denom, data)


# pass band frequency
PASS_BAND_FREQ = 40.0


def _adapt_signal(channel_definition, signal, sampling_frequency):
    factor = 1.0
    if channel_definition.get("ChannelSensitivity"):
        factor = float(channel_definition.ChannelSensitivity) * float(
            channel_definition.ChannelSensitivityCorrectionFactor
        )

    baseln = 0.0
    if channel_definition.get("ChannelBaseline"):
        baseln = float(channel_definition.get("ChannelBaseline"))

    units = channel_definition.ChannelSensitivityUnitsSequence[0].CodeValue
    amplifier = _get_amplifier(units)

    # generate the real signal values
    signal = (signal + baseln) * factor

    signal = (
        _butter_lowpass_filter(np.asarray(signal), PASS_BAND_FREQ, sampling_frequency, order=2)
        * amplifier
    )

    return signal


def convert_dicom(file_path: str) -> HolterCreate:
    """
    given a file path to a DICOM file
    open the file, extract the signal and other metadata
    adapt the signal and convert to the Willem API payload
    """
    try:
        dicom_ecg = dicom.read_file(file_path)
    except dicom.filereader.InvalidDicomError as err:
        raise Exception(err)

    sequence_item = dicom_ecg.WaveformSequence[0]

    # assumes 16 bits integers data
    channel_definitions = sequence_item.ChannelDefinitionSequence
    number_channels = sequence_item.NumberOfWaveformChannels
    samples = sequence_item.NumberOfWaveformSamples
    sampling_frequency = sequence_item.SamplingFrequency

    waveform_data = sequence_item.WaveformData
    unpack_fmt = "<%dh" % (len(waveform_data) / 2)
    unpacked_waveform_data = struct.unpack(unpack_fmt, waveform_data)
    signals = (
        np.asarray(unpacked_waveform_data, dtype=np.float32)
        .reshape(samples, number_channels)
        .transpose()
    )

    # this is a bit empirical
    # provide a value so that the average amplitude of your signal * corrective_factor are between -5 and 5
    corrective_factor = 0.005

    channels = []
    for index in range(number_channels):
        channel = channel_definitions._list[index]
        channel_name = channel.ChannelSourceSequence._list[0].CodeMeaning.replace("Lead", "").strip()
        signal = _adapt_signal(
            channel_definition=channel,
            signal=signals[index],
            sampling_frequency=sampling_frequency,
        )
        signal_list = [int(x) for x in signal.tolist()]
        channels.append(
            Channel(
                name=channel_name,
                sample_frequency=sampling_frequency,
                factor=corrective_factor,
                num_samples=samples,
                signal=signal_list,
            )
        )

    holter_create = HolterCreate(
        date=datetime.utcnow(),
        device=Device(
            name=dicom_ecg.ManufacturerModelName,
            company=dicom_ecg.Manufacturer,
            firmware=dicom_ecg.SeriesNumber,
            serial_number=dicom_ecg.DeviceSerialNumber
        ),
        channels=channels,
    )

    return holter_create.json()
