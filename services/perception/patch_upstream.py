"""Apply the AV-HuBERT video-only encoder fix required by upstream's README."""
from pathlib import Path
p = Path('/opt/av_hubert/avhubert/hubert.py')
s = p.read_text()
old = "        features_audio = self.forward_features(src_audio, modality='audio') # features: [B, F, T]\n        features_video = self.forward_features(src_video, modality='video')"
new = "        features_video = self.forward_features(src_video, modality='video')\n        features_audio = self.forward_features(src_audio, modality='audio') if src_audio is not None else torch.zeros_like(features_video)"
if s.count(old) != 1:
    raise RuntimeError('Pinned AV-HuBERT patch context changed')
p.write_text('# Modified by Alizé Lab: video-only AV-HuBERT initialization compatibility.\n' + s.replace(old, new))

# This pinned 2021 Fairseq predates NumPy 1.24. Replace removed scalar aliases
# without downgrading the ARM64 scientific runtime or altering tensor precision.
import re
import site
roots = [Path('/opt/av_hubert/fairseq/fairseq'), *(Path(root) / 'fairseq' for root in site.getsitepackages())]
for root in roots:
    for source in root.rglob('*.py'):
        before = source.read_text()
        after = re.sub(r'\bnp\.(float|int|bool|complex|object|str)\b', lambda m: m[1], before)
        if before != after:
            source.write_text('# Modified by Alizé Lab: removed NumPy scalar alias compatibility.\n' + after)
