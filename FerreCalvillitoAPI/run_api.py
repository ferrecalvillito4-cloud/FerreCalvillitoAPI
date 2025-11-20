import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Necesario para Render
        port=port,
        reload=False     # Render NO permite reload
    )
