from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <body>
            <h1>Hello, World!</h1>
        </body>
    </html>
    """

@app.get("/json", response_class=JSONResponse) # Not supported symbian browser
async def get_json():
    data = {
        "message": "Hello, World!",
        "status": "success",
        "data": {
            "key1": "value1",
            "key2": "value2"
        }
    }
    return data

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
