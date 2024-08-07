import numpy as np
from torch import Tensor
import torch
from torch.utils.mobile_optimizer import optimize_for_mobile
from pydub import AudioSegment
import librosa
from torch.quantization import per_channel_dynamic_qconfig
from torch.quantization import quantize_dynamic_jit
from SpeechRecognizer import SpeechRecognizer

def convert_samples_to_float32(samples):
    """
    Convert audio samples to float32 format. This function normalizes integer samples to the range [-1, 1].

    Parameters:
    samples (np.ndarray): Input audio samples.

    Returns:
    np.ndarray: Audio samples in float32 format.
    """
    float32_samples = samples.astype('float32')
    if samples.dtype in np.sctypes['int']:
        bits = np.iinfo(samples.dtype).bits
        float32_samples *= 1.0 / 2 ** (bits - 1)
    elif samples.dtype in np.sctypes['float']:
        pass
    else:
        raise TypeError("Unsupported sample type: %s." % samples.dtype)
    return float32_samples

def load_audio(audio_file):
    """
    Load and preprocess an audio file. The function converts the audio to mono, resamples to 16 kHz, and converts
    samples to float32 format suitable for deep learning models.

    Parameters:
    audio_file (str): Path to the audio file.

    Returns:
    tuple: A tuple containing:
        - features (torch.Tensor): Preprocessed audio features.
        - length (torch.Tensor): Length of the audio sequence.
    """
    samples = AudioSegment.from_file(audio_file)
    sample_rate = samples.frame_rate
    target_sr = 16000
    num_channels = samples.channels
  
    # Concatenate channels if there are multiple channels
    if num_channels > 1:
        samples = samples.set_channels(1)

    samples = np.array(samples.get_array_of_samples())  

    samples = convert_samples_to_float32(samples)
    if target_sr is not None and target_sr != sample_rate:
        samples = librosa.core.resample(samples, orig_sr=sample_rate, target_sr=target_sr)
        sample_rate = target_sr
    features = torch.tensor(samples, dtype=torch.float).unsqueeze(0)
    length = torch.tensor([features.shape[1]]).long()
    return features, length

if __name__ == "__main__":
    """
    Main function to load a pre-trained speech recognition model, preprocess audio files, quantize the model for mobile,
    and save the optimized model.
    """
    vocabulary = torch.load("Path_to_Vocab.pt")
    preprocessor = torch.jit.load("Path_to_CPU_model_preprocessor", map_location="cpu")
    scripted_model = torch.jit.load("Path_to_CPU_model", map_location="cpu")

    torch.backends.quantized.engine = 'qnnpack'
    model = SpeechRecognizer(scripted_model, preprocessor, vocabulary)
    scripted_model = torch.jit.script(model)

    quantized_model = quantize_dynamic_jit(scripted_model, {'': per_channel_dynamic_qconfig})

    optimized_model = optimize_for_mobile(quantized_model)

    torch.jit.save(quantized_model, "Path_to_save_dynamic_quantized_model")
