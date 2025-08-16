from fastapi import FastAPI, Request, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import json
import tempfile
from dotenv import load_dotenv
from audio_to_text import transcribe_audio
import utils
from weather_tool import weather_openmeteo
load_dotenv()

client = utils.get_client()

lat = "not provided"
lon = "not provided"
lang = "NA"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

chat_history = []

@app.post("/api/chat/stream")
async def chat_stream(req: Request):
    body = await req.json()
    message = body.get("message", "")

    if "XYABDDE" in message:
        global lat, lon
        lat = message.split(':')[1]
        lon = message.split(':')[-1]
        print(f"lat: {lat}, lon: {lon}")
        return JSONResponse({"status": "ok"})

    async def event_stream():
        yield f"{json.dumps({'type': 'progress', 'content': 'Translating to your language...'})}\n"
        # _, response = translate_query(message)
        response = message  # For now, just echo the message
        yield f"{json.dumps({'type': 'reply', 'content': f'{response}'})}\n"

    return StreamingResponse(event_stream(), media_type="text/plain")

@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(None),
    image: UploadFile = File(None),
    text: str = Form(None)
):
    contents = None
    if audio:
        contents = await audio.read()
    image_path = None
    if image:
        with tempfile.NamedTemporaryFile(delete=False, suffix=image.filename) as tmp:
            img_contents = await image.read()
            tmp.write(img_contents)
            image_path = tmp.name

    async def event_stream():
        txt = ""
        image_desc = ""

        if audio:
            yield f"{json.dumps({'type': 'progress', 'content': 'Transcribing audio...'})}\n"
            txt = await transcribe_audio(contents)

        if image_path:
            yield f"{json.dumps({'type': 'progress', 'content': 'Processing image...'})}\n"
            img_file = client.files.upload(file=image_path)
            img_prompt = "Can you give me a detailed description about the crop, the type of disease or pest that has affected the crop? Answer 'No disease/pest found' if the crop is healthy. Also mention the general health of the crop."
            img_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[img_prompt, img_file]
            )
            image_desc = img_result.text

        # If both image and audio, combine for agent response
        if image_desc and txt:
            yield f"{json.dumps({'type': 'progress', 'content': 'Generating response from image and audio...'})}\n"
            agent_prompt = f"Image Description: {image_desc}\nQuery: {txt}\nBased on the image and the query, provide a helpful, concise agricultural response."
            agent_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[agent_prompt]
            )
            combined_reply = agent_result.text
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"
        elif image_desc:
            combined_reply = f"Image Description: {image_desc}"
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"
        elif txt:
            # Only audio: pass transcript through agent for response
            yield f"{json.dumps({'type': 'progress', 'content': 'Generating response from audio query...'})}\n"
            agent_prompt = f"Query: {txt}\nBased on the query, provide a helpful, concise agricultural response."
            agent_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[agent_prompt]
            )
            combined_reply = agent_result.text
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"
        elif text:
            combined_reply = f"Query: {text}"
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"

    return StreamingResponse(event_stream(), media_type="text/plain")

@app.post("/api/chat/image")
async def chat_image(image: UploadFile = File(None), text: str = Form(None)):
    global chat_history
    image_path = None
    if image:
        with tempfile.NamedTemporaryFile(delete=False, suffix=image.filename) as tmp:
            contents = await image.read()
            tmp.write(contents)
            image_path = tmp.name

    async def event_stream():
        global chat_history
        image_desc = ""
        if image_path:
            yield f"{json.dumps({'type': 'progress', 'content': 'Processing image...'})}\n"
            img_file = client.files.upload(file=image_path)
            img_prompt = "Can you give me a detailed description about the crop, the type of disease or pest that has affected the crop? Answer 'No disease/pest found' if the crop is healthy. Also mention the general health of the crop."
            img_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[img_prompt, img_file]
            )
            image_desc = img_result.text

        # Always pass through agent, regardless of language
        if text and image_desc:
            yield f"{json.dumps({'type': 'progress', 'content': 'Generating response from image and text...'})}\n"
            # Add user message and image description to history
            chat_history.append({"role": "user", "type": "image", "content": image_desc})
            chat_history.append({"role": "user", "type": "text", "content": text})
            # Build context for agent
            context = ""
            for msg in chat_history[-10:]:
                if msg["type"] == "text":
                    context += f"{msg['role'].capitalize()}: {msg['content']}\n"
                elif msg["type"] == "image":
                    context += f"{msg['role'].capitalize()} (image description): {msg['content']}\n"
            agent_prompt = f"{context}Image Description: {image_desc}\nQuery: {text}\nBased on the image, the query, and previous conversation, provide a helpful, concise agricultural response."
            agent_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[agent_prompt]
            )
            combined_reply = agent_result.text
            chat_history.append({"role": "assistant", "type": "text", "content": combined_reply.strip()})
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"
        elif image_desc:
            chat_history.append({"role": "user", "type": "image", "content": image_desc})
            combined_reply = f"Image Description: {image_desc}"
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"
        elif text:
            yield f"{json.dumps({'type': 'progress', 'content': 'Generating response from query...'})}\n"
            chat_history.append({"role": "user", "type": "text", "content": text})
            # Build context for agent
            context = ""
            for msg in chat_history[-10:]:  # last 10 messages for context
                if msg["type"] == "text":
                    context += f"{msg['role'].capitalize()}: {msg['content']}\n"
                elif msg["type"] == "image":
                    context += f"{msg['role'].capitalize()} (image description): {msg['content']}\n"
            agent_prompt = f"{context}Query: {text}\nBased on the query and previous conversation, provide a helpful, concise agricultural response."
            agent_result = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[agent_prompt]
            )
            combined_reply = agent_result.text
            chat_history.append({"role": "assistant", "type": "text", "content": combined_reply.strip()})
            yield f"{json.dumps({'type': 'reply', 'content': combined_reply.strip()})}\n"

    return StreamingResponse(event_stream(), media_type="text/plain")

@app.get("/api/weather")
async def get_weather(lat: float = Query(...), lon: float = Query(...)):
    try:
        summary = weather_openmeteo(lat, lon)
        return summary
    except Exception as e:
        return {"error": str(e)}
