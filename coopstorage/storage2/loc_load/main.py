from typing import Union, Tuple
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class UnitOfMeasure(BaseModel):
    each_qty: int = 1
    dimensions: Tuple[float,float,float] = None

class Load(BaseModel):
    uom: str

UOMS = {}
LOADS = {}


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/uoms/{uom}")
def get_uom(uom: str):
    return {"uom_name": uom,
            "details": UOMS[uom]}

@app.get("/uoms")
def get_uoms():
    return UOMS

@app.put("/uoms/{uom_name}")
def put_uom(uom_name: str, uom: UnitOfMeasure):
    print("UOM Put")
    UOMS[uom_name] = uom
    return {"uom_name": uom_name, "details": uom}

@app.get("/loads/{lpn}")
def get_load(lpn: str,):
    return {"lpn": lpn,
            "details": LOADS[lpn]}

@app.get("/loads")
def get_loads():
    return LOADS

@app.put("/loads/{lpn}")
def put_load(lpn: str, load: Load):
    LOADS[lpn] = load
    return LOADS[lpn]

if __name__ == "__main__":
    import uvicorn

    put_uom("123", UnitOfMeasure(each_qty=1, dimensions=(10, 10, 10)))
    put_uom("234", UnitOfMeasure(each_qty=1, dimensions=(20, 10, 10)))
    put_uom("345", UnitOfMeasure(each_qty=1, dimensions=(30, 10, 10)))
    put_load("A1", Load(uom=123))

    uvicorn.run(
        "main:app",
        port=5000,
        log_level="info",
        reload=True
    )