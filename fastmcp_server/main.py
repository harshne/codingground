import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from nova_act import NovaAct

# Check for the API key at startup
if "NOVA_ACT_API_KEY" not in os.environ:
    raise RuntimeError("The NOVA_ACT_API_KEY environment variable is not set.")

app = FastAPI(
    title="FastMCP Server",
    description="A server to interact with nova-act using a Model Context Protocol.",
    version="1.0.0",
)

# In-memory storage for NovaAct sessions
sessions = {}

class StartSessionRequest(BaseModel):
    start_url: str

class ActRequest(BaseModel):
    command: str

@app.post("/session/start", summary="Start a new NovaAct session")
async def start_session(request: StartSessionRequest):
    """
    Starts a new NovaAct session and returns a session ID.
    """
    session_id = str(uuid.uuid4())
    try:
        nova = NovaAct(starting_page=request.start_url)
        nova.start()
        sessions[session_id] = nova
        return {"session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start NovaAct session: {e}")

@app.post("/session/{session_id}/act", summary="Perform an action in a session")
async def act(session_id: str, request: ActRequest):
    """
    Performs a natural language action in the specified NovaAct session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    nova = sessions[session_id]
    try:
        result = nova.act(request.command)
        return {"response": result.response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform action: {e}")

@app.get("/session/{session_id}/screenshot", summary="Take a screenshot")
async def screenshot(session_id: str):
    """
    Takes a screenshot of the current page in the specified NovaAct session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    nova = sessions[session_id]
    try:
        screenshot_bytes = nova.page.screenshot()
        return {"screenshot": screenshot_bytes.hex()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to take screenshot: {e}")

@app.post("/session/{session_id}/stop", summary="Stop a session")
async def stop_session(session_id: str):
    """
    Stops the specified NovaAct session and cleans up resources.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    nova = sessions.pop(session_id)
    try:
        nova.stop()
        return {"message": "Session stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop session: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
