import restate
from fastapi import FastAPI

app = FastAPI()

greeter = restate.Service("Greeter")


@greeter.handler()
async def greet(ctx: restate.Context, name: str) -> str:
    return f"Hello, {name}!"


restate_app = restate.app(services=[greeter])

app.mount("/restate", restate_app)


@app.get("/health")
async def health():
    return {"status": "ok"}
