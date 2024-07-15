import numpy as np
from torch import Tensor
import torch
from pydub import AudioSegment
import librosa
from torch.utils.mobile_optimizer import optimize_for_mobile
import pandas as pd
from SpeechRecognizer import SpeechRecognizer

def convert_samples_to_float32(samples):
    """
    Convert audio samples to float32 format.
    
    Parameters:
    samples (np.ndarray): The audio samples.

    Returns:
    np.ndarray: The converted float32 audio samples.
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
    Load and preprocess an audio file.
    
    Parameters:
    audio_file (str): Path to the audio file.

    Returns:
    Tuple[Tensor, Tensor]: Preprocessed audio features and their lengths.
    """
    samples = AudioSegment.from_file(audio_file)
    sample_rate = samples.frame_rate
    target_sr = 16000
    num_channels = samples.channels

    if num_channels > 1:
        samples = samples.set_channels(1)
    samples = np.array(samples.get_array_of_samples())

    # Convert samples to float32
    samples = convert_samples_to_float32(samples)

    # Resample if necessary
    if target_sr is not None and target_sr != sample_rate:
        samples = librosa.core.resample(samples, orig_sr=sample_rate, target_sr=target_sr)
        sample_rate = target_sr

    features = torch.tensor(samples, dtype=torch.float).unsqueeze(0)
    length = torch.tensor([features.shape[1]]).long()
    return features, length

class AudioDataset(torch.utils.data.Dataset):
    """
    A custom Dataset class for loading audio data and transcripts.
    """
    def __init__(self, audio_files, transcripts):
        """
        Initialize the dataset with a list of audio files and corresponding transcripts.

        Parameters:
        audio_files (List[str]): List of paths to audio files.
        transcripts (List[str]): List of transcripts corresponding to the audio files.
        """
        self.audio_files = audio_files
        self.transcripts = transcripts
    
    def __len__(self):
        """
        Return the number of samples in the dataset.
        
        Returns:
        int: Number of samples.
        """
        return len(self.audio_files)

    def __getitem__(self, index):
        """
        Get a sample from the dataset.

        Parameters:
        index (int): Index of the sample to retrieve.

        Returns:
        Tuple[Tensor, Tensor, str]: Preprocessed audio features, their lengths, and the corresponding transcript.
        """
        audio_file = self.audio_files[index]
        transcript = self.transcripts[index]
        f, fl = load_audio(audio_file)
        return f, fl, transcript

if __name__ == "__main__":
    # Set the quantized engine to 'qnnpack' for mobile or ARM-based devices
    torch.backends.quantized.engine = 'qnnpack'

    # Load and script the model
    model = torch.jit.load("Path_to_model_static_cpu.pt")
    scripted_model = torch.jit.script(model)

    # Optimize the model for mobile
    optimized_model = optimize_for_mobile(scripted_model)

    # Save the optimized model for lite interpreter
    optimized_model._save_for_lite_interpreter("lite_static.ptl")
