"""Bounded decoding and AV-HuBERT mouth preprocessing. Never accepts remote URLs."""
import importlib.util
import json
import math
import subprocess
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
MAX_SECONDS = 15

class MediaError(ValueError):
    pass


def inspect_media(path):
    try:
        p = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, timeout=12, check=True)
        data = json.loads(p.stdout)
        streams = data.get('streams', [])
        videos = [s for s in streams if s.get('codec_type') == 'video']
        if len(videos) != 1 or len(streams) > 2:
            raise MediaError('Utilisez une vidéo avec un seul visage et au plus une piste audio.')
        video = videos[0]
        duration = float(data.get('format', {}).get('duration') or video.get('duration') or 0)
        width, height = int(video.get('width', 0)), int(video.get('height', 0))
        if not math.isfinite(duration) or not .4 <= duration <= MAX_SECONDS:
            raise MediaError('La séquence doit durer entre 0,4 et 15 secondes.')
        if min(width, height) < 88 or width * height > 1920 * 1080:
            raise MediaError('Utilisez une vidéo entre 88 pixels et Full HD.')
        if video.get('codec_name') not in {'h264', 'hevc', 'vp8', 'vp9', 'av1', 'mpeg4'}:
            raise MediaError('Codec vidéo non pris en charge. Utilisez MP4 ou WebM.')
        return {'duration_seconds': duration, 'width': width, 'height': height, 'has_audio': any(s.get('codec_type') == 'audio' for s in streams)}
    except MediaError:
        raise
    except (ValueError, KeyError, subprocess.SubprocessError):
        raise MediaError('Le fichier ne contient pas de vidéo lisible.') from None


def normalize_video(path, target, mouth=False):
    scale = 'scale=96:96' if mouth else 'scale=w=min(640\\,iw):h=-2'
    subprocess.run(['ffmpeg', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-an', '-vf', 'fps=25,' + scale, '-t', str(MAX_SECONDS), '-frames:v', str(MAX_SECONDS * 25), '-threads', '2', '-y', str(target)], capture_output=True, timeout=30, check=True)


def mouth_frames(path, model_dir, framing):
    import cv2
    import numpy as np
    import dlib
    cap = cv2.VideoCapture(str(path))
    frames = []
    while len(frames) <= MAX_SECONDS * 25:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not 10 <= len(frames) <= MAX_SECONDS * 25:
        raise MediaError('Nombre de trames vidéo invalide.')
    if framing == 'face':
        detector = dlib.get_frontal_face_detector()
        predictor = dlib.shape_predictor(str(Path(model_dir) / 'shape_predictor_68_face_landmarks.dat'))
        landmarks = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = detector(gray, 0)
            if len(rects) > 1:
                raise MediaError('Plusieurs visages détectés. Enregistrez une seule personne face caméra.')
            if not rects:
                landmarks.append(None)
                continue
            shape = predictor(gray, rects[0])
            landmarks.append(np.array([(shape.part(i).x, shape.part(i).y) for i in range(68)]))
        detected = sum(value is not None for value in landmarks)
        if detected < max(5, len(frames) * .8):
            raise MediaError('Visage insuffisamment visible. Regardez la caméra, améliorez l’éclairage et recommencez.')
        spec = importlib.util.spec_from_file_location('avhubert_align_mouth', '/opt/av_hubert/avhubert/preparation/align_mouth.py')
        align = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(align)
        landmarks = align.landmarks_interpolate(landmarks)
        reference = np.load(Path(model_dir) / '20words_mean_face.npy', allow_pickle=False)
        frames = align.crop_patch(str(path), landmarks, reference, [33, 36, 39, 42, 45], (256, 256), 12, 48, 68, 96, 96)
        quality = {'preprocessing': 'dlib68_avhubert_alignment', 'face_detection_ratio': round(detected / len(landmarks), 3)}
    else:
        quality = {'preprocessing': 'user_supplied_mouth_crop', 'face_detection_ratio': None}
    gray = np.stack([cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames])
    # Match upstream load_video_feats(): 96 -> central 88 pixels; mean/std from AV-HuBERT.
    video = ((gray[:, 4:92, 4:92].astype(np.float32) / 255.0) - .421) / .165
    return video, quality
