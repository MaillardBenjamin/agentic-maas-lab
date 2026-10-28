"""One short-lived, local-only real inference process; released after each clip."""
import argparse
import json
import os
import time
from pathlib import Path

from media import MediaError, inspect_media, mouth_frames, normalize_video


def run(path, mode, framing, language, model_dir):
    import numpy as np
    import torch
    import whisper
    from whisper.model import ModelDimensions, Whisper
    torch.set_num_threads(3)
    torch.set_num_interop_threads(1)
    started = time.monotonic()
    metadata = inspect_media(path)
    if mode == 'avsr' and not metadata['has_audio']:
        raise MediaError('Cette vidéo n’a pas de son. Choisissez Lèvres seules ou ajoutez une piste audio.')
    normalized = Path(path).with_name('normalized.mp4')
    normalize_video(path, normalized, mouth=framing == 'mouth')
    video, quality = mouth_frames(normalized, model_dir, framing)
    preprocess_ms = round((time.monotonic() - started) * 1000)
    model_start = time.monotonic()
    # Construct the exact Small architecture directly: no hidden Whisper download.
    dims = ModelDimensions(n_mels=80, n_audio_ctx=1500, n_audio_state=768, n_audio_head=12, n_audio_layer=12, n_vocab=51865, n_text_ctx=448, n_text_state=768, n_text_head=12, n_text_layer=12)
    model = Whisper(dims, 0.0, True, str(Path(model_dir) / 'mavhubert_only_weights.pt'), '/opt/av_hubert/avhubert', 0.0, 0.0, True, 'separate', False, 256, 1)
    checkpoint = torch.load(Path(model_dir) / 'whisper-flamingo_multi-all_small.pt', map_location='cpu', mmap=True, weights_only=True)
    weights = checkpoint['state_dict']
    # A partial load would silently leave random visual weights. Require every parameter.
    model.load_state_dict({key.removeprefix('model.'): value for key, value in weights.items()}, strict=True)
    del checkpoint, weights
    model.eval()
    load_ms = round((time.monotonic() - model_start) * 1000)
    if mode == 'avsr':
        audio = whisper.load_audio(str(path))
    else:
        # No decoded microphone/audio samples enter the VSR path. Match the training
        # modality dropout by zeroing encoded audio, not by feeding silent audio alone.
        audio = np.zeros(round(len(video) / 25 * 16000), dtype=np.float32)
    mel = whisper.log_mel_spectrogram(audio)
    tensor = torch.from_numpy(video).unsqueeze(0).unsqueeze(0)
    hook = None
    if mode == 'vsr':
        hook = model.encoder.register_forward_hook(lambda _module, _args, output: (torch.zeros_like(output[0]), output[1]))
    options = whisper.DecodingOptions(language=language, task='transcribe', fp16=False, without_timestamps=True, beam_size=None, sample_len=96)
    inference_start = time.monotonic()
    try:
        with torch.inference_mode():
            result = model.decode(mel, options, tensor)
    finally:
        if hook:
            hook.remove()
    text = result.text.strip()
    abstained = not text or (mode == 'avsr' and result.no_speech_prob > .8)
    return {
        'text': '' if abstained else text, 'abstained': abstained,
        'requires_confirmation': True, 'mode': 'real_model', 'engine': 'mwhisper-flamingo-small',
        'language': language, 'modality': mode, 'audio_used': mode == 'avsr', 'video_used': True,
        'source_revision': 'a0e7e47f9ab6e3f076ca3473812ce8c70003e1f1',
        'quality': quality, 'duration_seconds': round(metadata['duration_seconds'], 3),
        'metrics': {'avg_logprob': round(result.avg_logprob, 4), 'no_speech_prob': round(result.no_speech_prob, 4), 'calibrated_confidence': None},
        'timings_ms': {'preprocessing': preprocess_ms, 'model_load': load_ms, 'inference': round((time.monotonic() - inference_start) * 1000), 'total': round((time.monotonic() - started) * 1000)},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=['avsr', 'vsr'], required=True)
    parser.add_argument('--framing', choices=['face', 'mouth'], required=True)
    parser.add_argument('--language', choices=['fr', 'en', 'es', 'de', 'it', 'pt', 'el', 'ru', 'ar'], required=True)
    args = parser.parse_args()
    try:
        value = {'ok': True, 'result': run(args.input, args.mode, args.framing, args.language, os.environ.get('MODEL_DIR', '/models'))}
    except MediaError as exc:
        value = {'ok': False, 'error': str(exc)}
    except Exception as exc:
        # Diagnostics contain the exception type only; neither frames nor transcript.
        value = {'ok': False, 'error': 'Le moteur vidéo n’a pas abouti. Consultez le diagnostic local du service.', 'diagnostic': type(exc).__name__}
        if os.environ.get('PERCEPTION_DEBUG') == 'true':
            import traceback
            traceback.print_exc()
    Path(args.output).write_text(json.dumps(value, ensure_ascii=False))
