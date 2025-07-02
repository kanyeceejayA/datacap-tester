# ISP Data Cap Tester - Backend Service

A robust and feature-rich backend service for testing ISP data caps and monitoring internet speed in real-time. This system consists of independent processes that work together to provide comprehensive bandwidth monitoring and throttling detection.

## 🏗️ Architecture

```
┌─────────────────┐    subprocess    ┌──────────────────┐
│   server.py     ├─────────────────▶│  downloader.py   │
│ (Dashboard+API) │    start/stop    │  (Background)    │
└─────────────────┘                  └──────────────────┘
         │                                    │
         │ reads                              │ writes
         ▼                                    ▼
┌─────────────────────────────────────────────────────────┐
│                  data.json                              │
│ {"speed": 45.2, "total_gb": 12.5, "status": "running"} │
└─────────────────────────────────────────────────────────┘
```

## 📁 File Structure

```
datacap-tester/
├── server.py           # Web server + process manager (374 lines)
├── downloader.py       # Independent download worker (272 lines)
├── dashboard.html      # Web dashboard interface (396 lines)
├── data.json          # Shared data storage
├── config.json        # Configuration settings
├── requirements.txt   # Python dependencies
├── test_backend.py    # Backend test suite
└── README.md          # This file
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Tests (Optional)
```bash
python test_backend.py
```

### 3. Start the Server
```bash
python server.py
```

### 4. Access Dashboard
- Open your browser to `http://localhost:8000`
- The dashboard will load automatically
- Click "Start Test" to begin monitoring

## 🔧 Core Components

### server.py - Main Web Server
**Responsibilities:**
- Serve web dashboard at `http://localhost:8000`
- Manage `downloader.py` subprocess lifecycle
- Provide REST API endpoints
- WebSocket for real-time updates
- System information gathering

**Key Features:**
- ✅ Process management with graceful shutdown
- ✅ Real-time WebSocket updates
- ✅ External IP and ISP detection
- ✅ System resource monitoring
- ✅ Automatic browser launching

### downloader.py - Download Worker
**Responsibilities:**
- Continuous downloading from test servers
- Real-time speed calculation
- Throttling pattern detection
- Data persistence to JSON
- Signal-based pause/resume

**Key Features:**
- ✅ Async HTTP streaming with `httpx`
- ✅ Multiple fallback test URLs
- ✅ Intelligent throttling detection
- ✅ Rolling statistics windows
- ✅ Memory-efficient data handling
- ✅ Graceful error recovery

### dashboard.html - Web Interface
**Features:**
- ✅ Real-time speed monitoring
- ✅ Interactive charts with Chart.js
- ✅ System information display
- ✅ Control buttons (Start/Stop/Pause/Resume)
- ✅ Data cap progress tracking
- ✅ Throttling alerts
- ✅ Responsive mobile design

## 🌐 API Endpoints

### Core Control
- `POST /api/start` - Start download test
- `POST /api/stop` - Stop download test  
- `POST /api/pause` - Pause download test
- `POST /api/resume` - Resume download test
- `POST /api/reset` - Reset all statistics

### Data Retrieval
- `GET /api/stats` - Current download statistics
- `GET /api/system` - System and network information
- `WS /ws` - WebSocket for real-time updates

### API Response Example
```json
{
  "status": "running",
  "speed_mbps": 45.2,
  "total_gb": 12.5,
  "session_duration": 3600,
  "avg_speed": 42.1,
  "peak_speed": 98.3,
  "throttle_detected": false,
  "baseline_speed": 47.8,
  "cap_percentage": 25.0,
  "data_points": [...],
  "last_update": "2024-01-01T12:00:00Z"
}
```

## ⚙️ Configuration

### config.json
```json
{
  "test_urls": [
    "https://speed.cloudflare.com/__down?bytes=100000000",
    "https://proof.ovh.net/files/1Gb.dat",
    "http://speedtest.tele2.net/1GB.zip"
  ],
  "data_cap_gb": 50,
  "update_interval_seconds": 2,
  "throttle_threshold_percent": 30,
  "port": 8000
}
```

**Configuration Options:**
- `test_urls`: List of download test servers
- `data_cap_gb`: Data limit for testing (1-1000+ GB)
- `update_interval_seconds`: How often to save data
- `throttle_threshold_percent`: Sensitivity for throttling detection
- `port`: Web server port

## 🧪 Advanced Features

### Throttling Detection
The system implements sophisticated throttling detection:

1. **Baseline Establishment**: Records initial speed samples
2. **Rolling Analysis**: Monitors recent vs baseline performance  
3. **Threshold Detection**: Configurable sensitivity (default 30%)
4. **Pattern Recognition**: Identifies consistent speed drops

### Real-time Monitoring
- **Speed Sampling**: 30-sample rolling window
- **Data Points**: Up to 1000 chart points stored
- **WebSocket Updates**: 2-second real-time refresh
- **Chart Updates**: Smooth animations without flicker

### System Information
Automatically detects and displays:
- External IP address
- ISP name and organization
- Geographic location
- System resource usage
- Connection quality metrics

## 🔒 Security & Privacy

- **No Data Storage**: Downloads are streamed, not saved to disk
- **Local Only**: All data stays on your machine
- **No Tracking**: No analytics or external reporting
- **Open Source**: Full code transparency

## 🛠️ Development & Testing

### Running Tests
```bash
# Test core components
python test_backend.py

# Test with server running (in another terminal)
python server.py
python test_backend.py  # Will include API tests
```

### Manual Testing
```bash
# Start server
python server.py

# In another terminal, test individual components
python -c "import downloader; print('Downloader OK')"
python -c "import server; print('Server OK')"

# Test API endpoints
curl http://localhost:8000/api/stats
curl -X POST http://localhost:8000/api/start
```

## 📊 Performance & Specifications

### Resource Usage
- **CPU**: ~5-15% during active downloading
- **Memory**: ~50-100MB for both processes combined
- **Network**: Configurable, typically 10-100MB chunks
- **Storage**: Minimal (only JSON data files)

### Scaling
- **Data Cap Range**: 1GB to unlimited
- **Speed Range**: 1 Mbps to 1000+ Mbps tested
- **Session Duration**: Hours to days supported
- **Chart Performance**: Optimized for 1000+ data points

## 🔧 Troubleshooting

### Common Issues

**"Cannot connect to server"**
```bash
# Check if server is running
ps aux | grep python
# Kill existing processes if needed
pkill -f server.py
# Restart server
python server.py
```

**"Downloader not starting"**
```bash
# Check file permissions
ls -la downloader.py
# Test downloader directly
python downloader.py
```

**"Speed always shows 0"**
- Check internet connection
- Verify test URLs in config.json
- Check firewall/proxy settings

### Log Analysis
Both processes output detailed logs:
```bash
# Server logs
python server.py 2>&1 | tee server.log

# Downloader logs (when run directly)
python downloader.py 2>&1 | tee downloader.log
```

## 🚀 Production Deployment

### Systemd Service (Linux)
```ini
[Unit]
Description=ISP Data Cap Tester
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/datacap-tester
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Support
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "server.py"]
```

## 📈 Future Enhancements

- [ ] SQLite database for historical data
- [ ] Email/SMS alerts for throttling
- [ ] Multiple concurrent download streams
- [ ] Advanced analytics and reporting
- [ ] Mobile app companion
- [ ] Cloud sync capabilities

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `python test_backend.py`
4. Submit a pull request

## 📄 License

This project is open source. Use, modify, and distribute freely.

---

**Built with ❤️ for monitoring ISP behavior and data caps** 