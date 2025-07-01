#!/usr/bin/env python3
"""
Simple log streaming server using FastAPI WebSockets.
This server streams log files to connected clients.
"""

import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set, Optional, List
import uvicorn

LOG_DIR = "../logs"
MAX_INITIAL_LINES = 100
PORT = 9000

app = FastAPI(title="Log Streaming Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.log_subscribers: Dict[str, Set[WebSocket]] = {}
        self.tail_processes: Dict[str, asyncio.subprocess.Process] = {}
    
    async def connect(self, websocket: WebSocket, log_file: str):
        """Connect a client to a specific log file"""
        if log_file not in self.log_subscribers:
            self.log_subscribers[log_file] = set()
            
        self.log_subscribers[log_file].add(websocket)
        if log_file not in self.tail_processes:
            await self.start_tail_process(log_file)
    
    def disconnect(self, websocket: WebSocket, log_file: Optional[str] = None):
        """Disconnect a client"""
        if log_file:
            if log_file in self.log_subscribers:
                self.log_subscribers[log_file].discard(websocket)
                if not self.log_subscribers[log_file] and log_file in self.tail_processes:
                    self.stop_tail_process(log_file)
        else:
            for log_file in list(self.log_subscribers.keys()):
                self.log_subscribers[log_file].discard(websocket)
                
                # if no subscribers left, stop the tail process
                if not self.log_subscribers[log_file] and log_file in self.tail_processes:
                    self.stop_tail_process(log_file)
    
    async def broadcast(self, source: str, message: str):
        """Broadcast a message to all subscribers of a log file"""
        if source in self.log_subscribers:
            disconnected_clients = set()
            for websocket in self.log_subscribers[source]:
                try:
                    await websocket.send_text(json.dumps({
                        "source": source,
                        "content": message
                    }))
                except RuntimeError:
                    disconnected_clients.add(websocket)
            
            for client in disconnected_clients:
                self.disconnect(client, source)
    
    async def send_initial_logs(self, websocket: WebSocket, source: str, lines: int = MAX_INITIAL_LINES):
        """Send the initial logs to a newly connected client"""
        log_path = os.path.join(LOG_DIR, source)
       
        try:
            process = await asyncio.create_subprocess_exec(
                "tail", "-n", str(lines), log_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                await websocket.send_text(json.dumps({
                    "source": source,
                    "content": stdout.decode()
                }))
        except Exception as e:
            print(f"Error sending initial logs: {e}")
    
    async def start_tail_process(self, log_file: str):
        """Start a tail process for a log file"""
        log_path = os.path.join(LOG_DIR, log_file)

        process = await asyncio.create_subprocess_exec(
            "tail", "-n", "0", "-F", log_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        self.tail_processes[log_file] = process
        asyncio.create_task(self._read_tail_output(log_file, process))
    
    def stop_tail_process(self, log_file: str):
        """Stop a tail process"""
        if log_file in self.tail_processes:
            process = self.tail_processes[log_file]
            try:
                process.terminate()
            except:
                pass
            del self.tail_processes[log_file]
    
    async def _read_tail_output(self, log_file: str, process: asyncio.subprocess.Process):
        """Read and broadcast output from a tail process"""
        while True:
            line = await process.stdout.readline()
            if not line:
                break
                
            content = line.decode()
            await self.broadcast(log_file, content)

    def list_log_files(self) -> List[str]:
        """List available log files"""
        try:
            return [f for f in os.listdir(LOG_DIR) if f.endswith('.log')]
        except Exception as e:
            print(f"Error listing log files: {e}")
            return []

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Log streaming server is running. Connect via WebSocket at /ws"}

@app.post("/")
async def report(request: Request):
    data = await request.json()
    print(json.dumps(data, indent=4))
    await manager.broadcast("ERRORS", data)
    return {"message": "Report received and broadcasted"}

@app.websocket("/")
async def root_websocket_endpoint(websocket: WebSocket):
    print("WebSocket connection request received at /")
    await websocket.accept()
    print("WebSocket connection accepted at /")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received WebSocket message: {data}")
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
                continue
            
            message_type = message.get("type")
            
            if message_type == "subscribe":
                source = message.get("source")
                if not source:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "source is required"
                    }))
                    continue
                
                lines = int(message.get("lines", MAX_INITIAL_LINES))
                await manager.connect(websocket, source)
                await manager.send_initial_logs(websocket, source, lines)
                
            elif message_type == "unsubscribe":
                source = message.get("source")
                if not source:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "log_file is required"
                    }))
                    continue
                
                # Disconnect client from log file
                manager.disconnect(websocket, source)
                
            elif message_type == "list":
                files = await manager.list_log_files()
                await websocket.send_text(json.dumps({
                    "type": "list",
                    "files": files
                }))
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }))
    
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
        manager.disconnect(websocket)
        
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    print(f"Starting log server on port {PORT}")
    print(f"Log dir at: {LOG_DIR} with {manager.list_log_files()} available logs.")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
