from fastapi import FastAPI

app = FastAPI(
    title="IT HelpDesk Agent",
    description="Multi-agent IT support system",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}
