from fastapi import FastAPI

app = FastAPI(title="Azure Reliability Platform")


@app.get("/")
def root():
    return {"message": "Azure Reliability Platform is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}