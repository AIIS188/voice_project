# websocket_test_server.py
import asyncio
import websockets

async def handler(websocket, path):
    print(f"收到连接: {path}")
    
    try:
        # 发送初始消息
        await websocket.send("连接成功")
        print("发送了'连接成功'消息")
        
        # 接收和回显消息
        async for message in websocket:
            print(f"收到消息: {message}")
            await websocket.send(f"服务器收到: {message}")
    except Exception as e:
        print(f"处理连接时发生错误: {e}")
    finally:
        print("连接已关闭")

async def main():
    # 在端口8765上启动WebSocket服务器
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("WebSocket服务器已在ws://0.0.0.0:8765启动")
    
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())