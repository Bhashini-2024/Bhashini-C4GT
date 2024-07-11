import numpy as np
from torch import Tensor
import torch
from pydub import AudioSegment
import librosa
import json
import time
import jiwer 
import pandas as pd
from SpeechRecognizer import SpeechRecognizer


def convert_samples_to_float32(samples):
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
    def __init__(self, audio_files, transcripts):
        self.audio_files = audio_files
        self.transcripts = transcripts
    
    def __len__(self):
        return len(self.audio_files)

    def __getitem__(self, index):
        audio_file = self.audio_files[index]
        transcript = self.transcripts[index]
        f, fl = load_audio(audio_file)
        return f, fl, transcript


if __name__ == "__main__":

    torch.backends.quantized.engine = 'qnnpack' #mobile or arm based 

    model = torch.jit.load("Path_to_static_quantised_model.pt")
    scripted_model = torch.jit.script(model)

    # Load audio list from JSON
    with open("Path_to_data.json") as f:
        audio_list = json.load(f)
    audio_files = [ex["audio_filepath"] for ex in audio_list]
    transcripts = [ex["text"] for ex in audio_list]

    dataset = AudioDataset(audio_files, transcripts)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False)

    # Calculate WER on the dataset
    ground_truths = []
    predictions = []
    infer_time = []

    for data, lengths, trans in dataloader:
        with torch.no_grad():
            data = data.squeeze(0)
            lengths = lengths.squeeze(0)
            start = time.time()
            pred = model(data, lengths)
            end = time.time()
            predictions.append(pred)
            ground_truths.append(trans[0])
            infer_time.append(end-start)

    # Use jiwer to calculate WER
    wer = jiwer.wer(ground_truths, predictions)
    print(f"Word Error Rate (WER): {wer}")
    
    print("Average inference time : ",sum(infer_time)/len(infer_time))

    df = pd.read_csv("Path_to_predictions.csv")
    df = df.assign(static_quantised_cpu=predictions)
    print(df.head(5))
    df.to_csv("Path_to_predictions.csv")