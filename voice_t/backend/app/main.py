import uvicorn
from app.core.init import create_app
# 导入必要模块
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# Create the FastAPI application
app = create_app()


@app.get("/api/debug/routes")
async def debug_routes():
    """列出所有注册的路由"""
    routes = []
    
    for route in app.routes:
        route_info = {
            "path": getattr(route, "path", "unknown"),
            "name": getattr(route, "name", None),
            "endpoint": route.endpoint.__name__ if hasattr(route, "endpoint") else "unknown",
            "type": route.__class__.__name__
        }
        routes.append(route_info)
    
    # 打印到控制台
    for route in routes:
        print(f"路由: {route}")
    
    return {"routes": routes}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True
    )