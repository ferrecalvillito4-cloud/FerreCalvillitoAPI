import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    
    # Solo abrir navegador en desarrollo local
    if os.getenv("ENVIRONMENT", "development") == "development":
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # ⚠️ IMPORTANTE para Render
        port=port,
        reload=os.getenv("ENVIRONMENT") != "production"
    )