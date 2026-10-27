import logging
from fastapi import FastAPI
logging.basicConfig(level=logging.INFO)
app = FastAPI()
@app.get('/')
def test(): return 'ok'
