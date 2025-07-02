#!/usr/bin/env python3
"""
ISP Data Cap Tester - Main Server
Web server + process manager for the ISP data cap testing tool.
"""

import asyncio
import json
import os
import subprocess
import sys
import signal
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set
import requests
import psutil

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

class DataCapTesterServer:
    def __init__(self, config_path: str = "config.json", data_path: str = "data.json"):
        self.config_path = config_path
        self.data_path = data_path
        self.downloader_process: Optional[subprocess.Popen] = None
        self.websocket_connections: Set[WebSocket] = set()
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="ISP Data Cap Tester",
            description="Monitor and test your ISP's data cap and throttling behavior",
            version="1.0.0"
        )
        
        # Setup routes
        self.setup_routes()
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"port": 8000, "data_cap_gb": 50}

    def load_data(self) -> Dict:
        """Load current statistics from data.json and verify process status."""
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
            
            # Check if status says running/paused but no process is actually running
            if data.get("status") in ["running", "paused"] and not self.is_downloader_running():
                print("⚠️ Data file indicates running/paused status but no downloader process found - correcting status to stopped")
                data["status"] = "stopped"
                # Save the corrected status
                try:
                    with open(self.data_path, 'w') as f:
                        json.dump(data, f, indent=2)
                except:
                    pass  # Don't fail if we can't save the correction
            
            return data
        except Exception as e:
            print(f"Error loading data: {e}")
            return {
                "status": "stopped",
                "speed_mbps": 0.0,
                "total_gb": 0.0,
                "session_duration": 0,
                "avg_speed": 0.0,
                "peak_speed": 0.0,
                "throttle_detected": False,
                "last_update": None
            }

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop_downloader()
        sys.exit(0)

    def is_downloader_running(self) -> bool:
        """Check if downloader process is running."""
        if self.downloader_process is None:
            return False
        
        try:
            # Check if process is still alive
            if self.downloader_process.poll() is None:
                return True
            else:
                self.downloader_process = None
                return False
        except:
            self.downloader_process = None
            return False

    def start_downloader(self, fresh: bool = True) -> bool:
        """Start the downloader subprocess."""
        if self.is_downloader_running():
            print("Downloader already running")
            return True
        
        try:
            # Clean up any leftover signal files
            for signal_file in ["pause.signal", "resume.signal", "stop.signal"]:
                try:
                    Path(signal_file).unlink(missing_ok=True)
                except:
                    pass
            
            # Build command with proper arguments
            cmd = [sys.executable, "downloader.py"]
            if not fresh:  # Add resume flag only if not fresh
                cmd.append("--resume")
            
            print(f"Starting downloader with command: {' '.join(cmd)}")
            
            # Start downloader as subprocess - DON'T capture stdout/stderr
            # Let it write directly to console and log file
            self.downloader_process = subprocess.Popen(
                cmd,
                # Don't capture stdout/stderr - let downloader write directly
                stdout=None,
                stderr=None,
                # Create new process group for better process management
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Give it a moment to start
            time.sleep(0.5)
            
            # Check if it's still running
            if self.downloader_process.poll() is None:
                print(f"✅ Started downloader process (PID: {self.downloader_process.pid}) - {'Fresh' if fresh else 'Resume'} mode")
                return True
            else:
                print(f"❌ Downloader process exited immediately with code: {self.downloader_process.returncode}")
                self.downloader_process = None
                return False
                
        except Exception as e:
            print(f"❌ Error starting downloader: {e}")
            return False

    def stop_downloader(self) -> bool:
        """Stop the downloader subprocess."""
        if not self.is_downloader_running():
            print("Downloader not running")
            return True
        
        try:
            print(f"Stopping downloader process (PID: {self.downloader_process.pid})...")
            
            # On Windows, try to terminate gracefully first
            if os.name == 'nt':
                # Send Ctrl+C signal to the process group
                try:
                    self.downloader_process.send_signal(signal.CTRL_C_EVENT)
                    print("Sent Ctrl+C signal to downloader")
                except:
                    # Fallback to terminate
                    self.downloader_process.terminate()
                    print("Sent terminate signal to downloader")
            else:
                # Send SIGTERM for graceful shutdown on Unix
                self.downloader_process.terminate()
                print("Sent SIGTERM to downloader")
            
            # Wait up to 8 seconds for graceful shutdown
            try:
                exit_code = self.downloader_process.wait(timeout=8)
                print(f"✅ Downloader process stopped gracefully (exit code: {exit_code})")
            except subprocess.TimeoutExpired:
                # Force kill if not stopped gracefully
                print("⚠️ Downloader didn't stop gracefully, force killing...")
                self.downloader_process.kill()
                exit_code = self.downloader_process.wait()
                print(f"💀 Downloader process force killed (exit code: {exit_code})")
            
            self.downloader_process = None
            return True
            
        except Exception as e:
            print(f"❌ Error stopping downloader: {e}")
            self.downloader_process = None  # Clear it anyway
            return False

    def pause_downloader(self) -> bool:
        """Pause the downloader by creating a signal file."""
        try:
            Path("pause.signal").touch()
            print("Pause signal sent to downloader")
            return True
        except Exception as e:
            print(f"Error pausing downloader: {e}")
            return False

    def resume_downloader(self) -> bool:
        """Resume the downloader by creating a signal file."""
        try:
            Path("resume.signal").touch()
            print("Resume signal sent to downloader")
            return True
        except Exception as e:
            print(f"Error resuming downloader: {e}")
            return False

    def get_system_info(self) -> Dict:
        """Get system and network information."""
        try:
            # Get external IP and ISP info
            ip_response = requests.get("http://httpbin.org/ip", timeout=5)
            ip_data = ip_response.json()
            external_ip = ip_data.get("origin", "Unknown")
            
            # Get location and ISP info
            try:
                location_response = requests.get(f"http://ip-api.com/json/{external_ip}", timeout=5)
                location_data = location_response.json()
            except:
                location_data = {}
            
            # Get system info
            system_info = {
                "external_ip": external_ip,
                "isp": location_data.get("isp", "Unknown"),
                "org": location_data.get("org", "Unknown"),
                "city": location_data.get("city", "Unknown"),
                "region": location_data.get("regionName", "Unknown"),
                "country": location_data.get("country", "Unknown"),
                "timezone": location_data.get("timezone", "Unknown"),
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent if os.name != 'nt' else psutil.disk_usage("C:\\").percent,
                "downloader_running": self.is_downloader_running()
            }
            
            return system_info
            
        except Exception as e:
            print(f"Error getting system info: {e}")
            return {
                "external_ip": "Unknown",
                "isp": "Unknown",
                "downloader_running": self.is_downloader_running()
            }

    async def broadcast_to_websockets(self, data: Dict):
        """Broadcast data to all connected WebSocket clients."""
        if not self.websocket_connections:
            return
        
        message = json.dumps(data)
        disconnected = set()
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except:
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.websocket_connections -= disconnected

    def setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def serve_dashboard():
            """Serve the main dashboard HTML."""
            try:
                return FileResponse("dashboard.html")
            except FileNotFoundError:
                return HTMLResponse("""
                <html>
                <head><title>ISP Data Cap Tester</title></head>
                <body>
                    <h1>ISP Data Cap Tester</h1>
                    <p>Dashboard not found. Please create dashboard.html</p>
                    <p>Server is running and API endpoints are available at /api/</p>
                </body>
                </html>
                """)

        @self.app.post("/api/start")
        async def start_test(request: Request):
            """Start the download test with optional configuration."""
            # Try to parse configuration from request body
            config = None
            try:
                body = await request.body()
                if body:
                    config = json.loads(body.decode('utf-8'))
            except:
                pass  # No config provided or invalid JSON
            
            # If config is provided, update the config file
            if config:
                try:
                    current_config = self.load_config()
                    current_config.update(config)
                    with open(self.config_path, 'w') as f:
                        json.dump(current_config, f, indent=2)
                    print(f"Updated configuration: {config}")
                except Exception as e:
                    print(f"Warning: Could not update config: {e}")
            
            if self.start_downloader(fresh=True):
                return {"success": True, "message": "Download test started"}
            else:
                raise HTTPException(status_code=500, detail="Failed to start downloader")

        @self.app.post("/api/start-resume")
        async def start_resume_test():
            """Resume previous download test."""
            if self.start_downloader(fresh=False):
                return {"success": True, "message": "Previous session resumed"}
            else:
                raise HTTPException(status_code=500, detail="Failed to resume downloader")

        @self.app.post("/api/stop")
        async def stop_test():
            """Stop the download test."""
            if self.stop_downloader():
                return {"success": True, "message": "Download test stopped"}
            else:
                raise HTTPException(status_code=500, detail="Failed to stop downloader")



        @self.app.get("/api/stats")
        async def get_stats():
            """Get current download statistics."""
            data = self.load_data()
            data["downloader_running"] = self.is_downloader_running()
            return data

        @self.app.get("/api/system")
        async def get_system():
            """Get system and network information."""
            return self.get_system_info()

        @self.app.get("/api/config")
        async def get_config():
            """Get current configuration."""
            return self.load_config()

        @self.app.post("/api/reset")
        async def reset_stats():
            """Reset statistics and stop any running test."""
            self.stop_downloader()
            
            # Reset data file
            reset_data = {
                "status": "stopped",
                "speed_mbps": 0.0,
                "total_gb": 0.0,
                "session_duration": 0,
                "avg_speed": 0.0,
                "peak_speed": 0.0,
                "throttle_detected": False,
                "last_update": None,
                "session_start": None,
                "data_points": [],
                "errors": []
            }
            
            try:
                with open(self.data_path, 'w') as f:
                    json.dump(reset_data, f, indent=2)
                return {"success": True, "message": "Statistics reset"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to reset stats: {e}")

        @self.app.post("/api/clear-errors")
        async def clear_errors():
            """Clear error log while preserving other data."""
            try:
                data = self.load_data()
                data["errors"] = []  # Clear errors only
                
                with open(self.data_path, 'w') as f:
                    json.dump(data, f, indent=2)
                return {"success": True, "message": "Errors cleared"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to clear errors: {e}")

        @self.app.post("/api/clear-logs")
        async def clear_logs():
            """Clear downloader log file."""
            try:
                log_file = Path("downloader.log")
                if log_file.exists():
                    log_file.unlink()  # Delete the log file
                    return {"success": True, "message": "Logs cleared"}
                else:
                    return {"success": True, "message": "No log file to clear"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to clear logs: {e}")

        @self.app.post("/api/save-config")
        async def save_config(request: Request):
            """Save configuration settings."""
            try:
                body = await request.body()
                if not body:
                    raise HTTPException(status_code=400, detail="No configuration data provided")
                
                config = json.loads(body.decode('utf-8'))
                
                # Load current config and update with new values
                current_config = self.load_config()
                current_config.update(config)
                
                # Save updated config
                with open(self.config_path, 'w') as f:
                    json.dump(current_config, f, indent=2)
                
                print(f"Configuration saved: {config}")
                return {"success": True, "message": "Configuration saved successfully"}
                
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON data")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")

        @self.app.get("/api/can-resume")
        async def can_resume():
            """Check if there's a previous session to resume."""
            try:
                data = self.load_data()
                has_data = (data.get("total_gb", 0) > 0 or 
                           data.get("session_duration", 0) > 0 or
                           len(data.get("data_points", [])) > 0)
                return {"can_resume": has_data, "previous_data": data if has_data else None}
            except:
                return {"can_resume": False, "previous_data": None}

        @self.app.get("/api/logs")
        async def get_downloader_logs():
            """Get recent downloader logs."""
            try:
                log_file = Path("downloader.log")
                if log_file.exists():
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    # Return last 100 lines
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    return {
                        "success": True,
                        "logs": recent_lines,
                        "total_lines": len(lines)
                    }
                else:
                    return {
                        "success": True,
                        "logs": ["No log file found yet"],
                        "total_lines": 0
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "logs": [f"Error reading logs: {e}"],
                    "total_lines": 0
                }

        @self.app.get("/api/debug/test-downloader")
        async def test_downloader():
            """Test if downloader script can run independently (debug endpoint)."""
            try:
                # Test if we can run the downloader with --help
                result = subprocess.run(
                    [sys.executable, "downloader.py", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                return {
                    "success": True,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "python_path": sys.executable,
                    "current_dir": os.getcwd(),
                    "files_exist": {
                        "downloader.py": Path("downloader.py").exists(),
                        "config.json": Path("config.json").exists(),
                        "data.json": Path("data.json").exists()
                    }
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "python_path": sys.executable,
                    "current_dir": os.getcwd()
                }

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            try:
                # Send initial data
                initial_data = self.load_data()
                initial_data["downloader_running"] = self.is_downloader_running()
                await websocket.send_text(json.dumps(initial_data))
                
                # Keep connection alive and send updates
                while True:
                    # Wait for data updates or send periodic updates
                    await asyncio.sleep(2)
                    
                    # Send current stats
                    current_data = self.load_data()
                    current_data["downloader_running"] = self.is_downloader_running()
                    
                    # Double-check status consistency (extra safety)
                    if current_data.get("status") in ["running", "paused"] and not current_data["downloader_running"]:
                        current_data["status"] = "stopped"
                    
                    await websocket.send_text(json.dumps(current_data))
                    
            except WebSocketDisconnect:
                pass
            finally:
                self.websocket_connections.discard(websocket)

    def run(self, host: str = "localhost", port: int = None):
        """Run the server."""
        if port is None:
            port = self.config.get("port", 8000)
        
        print(f"Starting ISP Data Cap Tester server on http://{host}:{port}")
        
        # Try to open browser automatically
        try:
            webbrowser.open(f"http://{host}:{port}")
        except:
            pass
        
        # Run the server
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=False
        )

def main():
    """Main entry point."""
    server = DataCapTesterServer()
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server.stop_downloader()

if __name__ == "__main__":
    main() 