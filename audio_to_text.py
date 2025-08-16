from utils import get_client
import tempfile

async def transcribe_audio(contents):
    client = get_client()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
        tmp_file.write(contents)
        tmp_path = tmp_file.name
    audio_file = client.files.upload(file=tmp_path)
    print("I am here.")
    prompt = "Transcribe this audio into English."
    result = client.models.generate_content(
        model = "gemini-2.5-flash-lite",
        contents = [prompt, audio_file]
    )
    return result.text