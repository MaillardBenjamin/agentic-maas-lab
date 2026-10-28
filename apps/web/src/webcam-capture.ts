type RecorderRuntime = {
  stream: (tracks: MediaStreamTrack[]) => MediaStream;
  recorder: (stream: MediaStream, options?: MediaRecorderOptions) => MediaRecorder;
  supported: (mime: string) => boolean;
};

/** A phrase comes from the active webcam stream; this helper never opens files. */
export function recordWebcamPhrase(source: MediaStream, videoOnly: boolean, runtime?: Partial<RecorderRuntime>) {
  const env = {stream: (tracks: MediaStreamTrack[]) => new MediaStream(tracks), recorder: (stream: MediaStream, options?: MediaRecorderOptions) => new MediaRecorder(stream, options), supported: (mime: string) => MediaRecorder.isTypeSupported(mime), ...runtime};
  const capture = env.stream(videoOnly ? source.getVideoTracks() : source.getTracks());
  const mime = ['video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'].find(env.supported);
  const recorder = env.recorder(capture, mime ? {mimeType: mime, videoBitsPerSecond: 700000} : undefined);
  const chunks: Blob[] = [];
  let canceled = false, failed = false;
  const result = new Promise<Blob>((resolve, reject) => {
    recorder.ondataavailable = event => { if (event.data.size && !canceled && !failed) chunks.push(event.data); };
    recorder.onerror = () => { failed = true; chunks.length = 0; reject(new Error('La capture webcam n’a pas abouti. Recommencez.')); if (recorder.state === 'recording') recorder.stop(); };
    recorder.onstop = () => {
      if (canceled) reject(new DOMException('Capture annulée', 'AbortError'));
      else if (!failed) resolve(new Blob(chunks, {type: recorder.mimeType}));
      chunks.length = 0;
    };
  });
  recorder.start();
  return {recorder, result, cancel: () => { canceled = true; chunks.length = 0; if (recorder.state === 'recording') recorder.stop(); }};
}

export async function acquireWebcam(audio: boolean, current: () => boolean, getMedia = (constraints: MediaStreamConstraints) => navigator.mediaDevices.getUserMedia(constraints)): Promise<MediaStream | null> {
  const stream = await getMedia({video: {facingMode: 'user', width: {ideal: 640}, height: {ideal: 480}, frameRate: {ideal: 25}}, audio: audio ? {echoCancellation: true, noiseSuppression: true} : false});
  if (current()) return stream;
  stream.getTracks().forEach(track => track.stop());
  return null;
}
