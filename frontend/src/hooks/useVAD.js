export async function createVAD({ stream, onSpeechStart, onSpeechEnd }) {
  const instance = await vad.MicVAD.new({ stream, onSpeechStart, onSpeechEnd });
  return {
    start: () => instance.start(),
    pause: () => instance.pause(),
  };
}
