# main.py - FastAPI server for ADK agent
# Run with: uvicorn main:app --host 0.0.0.0 --port 8080
# Or: python main.py

from google.adk.api_server import create_api_server

# Creates FastAPI app with ADK endpoints
app = create_api_server()

@app.get("/health")
def health_check():
    """Health check endpoint for load balancers"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
