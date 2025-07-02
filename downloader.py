#!/usr/bin/env python3
"""
ISP Data Cap Tester - Download Worker
Independent process that downloads test data and tracks bandwidth usage.
"""

import asyncio
import json
import time
import signal
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import httpx
import statistics

# Setup logging to file with UTF-8 encoding for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log', encoding='utf-8'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

class DownloadTester:
    def __init__(self, config_path: str = "config.json", data_path: str = "data.json", resume_session: bool = False):
        self.config_path = config_path
        self.data_path = data_path
        self.running = False
        self.paused = False
        self.resume_session = resume_session
        
        # Load configuration
        self.config = self.load_config()
        
        # Statistics tracking
        self.total_bytes = 0
        self.session_start = None
        self.speed_samples = []
        self.data_points = []
        self.errors = []
        self.peak_speed = 0.0
        
        # Throttling detection
        self.speed_history = []
        self.baseline_speed = None
        self.throttle_detected = False
        
        # Speed performance tracking relative to expected speed
        self.expected_speed = self.config.get("expected_speed_mbps", 60)
        self.performance_samples = []  # Store performance category for each measurement
        self.performance_stats = {
            "close_to_expected": 0,      # Within ±20% of expected
            "far_below_expected": 0,     # Less than 80% of expected  
            "far_above_expected": 0      # More than 120% of expected
        }
        
        # Load previous state if resuming
        if self.resume_session:
            self.load_previous_state()
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {
                "test_urls": ["https://speed.cloudflare.com/__down?bytes=100000000"],
                "data_cap_gb": 50,
                "update_interval_seconds": 2,
                "throttle_threshold_percent": 30
            }

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    async def download_chunk(self, url: str, client: httpx.AsyncClient) -> tuple[int, float]:
        """Download a chunk from URL and return bytes downloaded and time taken."""
        chunk_size = 8192
        bytes_downloaded = 0
        start_time = time.time()
        
        try:
            async with client.stream('GET', url, timeout=30.0) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_bytes(chunk_size):
                    if not self.running or self.paused:
                        break
                    bytes_downloaded += len(chunk)
                    
                    # Don't download more than 100MB per request to avoid excessive usage
                    if bytes_downloaded >= 100 * 1024 * 1024:
                        break
                        
        except Exception as e:
            self.errors.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "url": url
            })
            logger.error(f"Download error: {e}")
            
        return bytes_downloaded, time.time() - start_time

    def calculate_speed(self, bytes_downloaded: int, time_taken: float) -> float:
        """Calculate download speed in Mbps."""
        if time_taken <= 0:
            return 0.0
        
        # Convert bytes to megabits and calculate speed
        megabits = (bytes_downloaded * 8) / (1024 * 1024)
        speed_mbps = megabits / time_taken
        return speed_mbps

    def categorize_speed_performance(self, speed_mbps: float) -> str:
        """Categorize speed performance relative to expected speed."""
        close_threshold_low = self.expected_speed * 0.8   # 80% of expected
        close_threshold_high = self.expected_speed * 1.2  # 120% of expected
        
        if speed_mbps < close_threshold_low:
            return "far_below_expected"
        elif speed_mbps > close_threshold_high:
            return "far_above_expected"
        else:
            return "close_to_expected"

    def update_statistics(self, speed_mbps: float):
        """Update rolling statistics and detect throttling."""
        now = datetime.now(timezone.utc)
        
        # Add to speed samples (keep last 30 samples)
        self.speed_samples.append(speed_mbps)
        if len(self.speed_samples) > 30:
            self.speed_samples.pop(0)
        
        # Update peak speed
        if speed_mbps > self.peak_speed:
            self.peak_speed = speed_mbps
        
        # Track performance relative to expected speed
        performance_category = self.categorize_speed_performance(speed_mbps)
        self.performance_samples.append(performance_category)
        
        # Keep only last 1000 performance samples to prevent memory issues
        if len(self.performance_samples) > 1000:
            self.performance_samples.pop(0)
        
        # Update performance statistics
        self.update_performance_stats()
        
        # Add data point for charting (including performance info)
        self.data_points.append({
            "timestamp": now.isoformat(),
            "speed_mbps": speed_mbps,
            "total_gb": self.total_bytes / (1024**3),
            "performance_category": performance_category,
            "expected_speed": self.expected_speed
        })
        
        # Keep only last 1000 data points to prevent memory issues
        if len(self.data_points) > 1000:
            self.data_points.pop(0)
        
        # Throttling detection
        self.detect_throttling(speed_mbps)

    def update_performance_stats(self):
        """Update percentage statistics for speed performance categories."""
        if not self.performance_samples:
            return
        
        total_samples = len(self.performance_samples)
        self.performance_stats = {
            "close_to_expected": (self.performance_samples.count("close_to_expected") / total_samples) * 100,
            "far_below_expected": (self.performance_samples.count("far_below_expected") / total_samples) * 100,
            "far_above_expected": (self.performance_samples.count("far_above_expected") / total_samples) * 100
        }

    def detect_throttling(self, current_speed: float):
        """Detect if ISP is throttling based on speed patterns over time."""
        now = datetime.now(timezone.utc)
        
        # Add speed with timestamp for time-based analysis
        self.speed_history.append({
            "speed": current_speed,
            "timestamp": now
        })
        
        # Keep only last 30 minutes of data (assuming ~2 second intervals)
        cutoff_time = now - timedelta(minutes=30)
        self.speed_history = [
            entry for entry in self.speed_history 
            if datetime.fromisoformat(entry["timestamp"].isoformat()) > cutoff_time
        ]
        
        if len(self.speed_history) < 10:
            return
        
        # Establish baseline from first 5 minutes of data
        if self.baseline_speed is None and len(self.speed_history) >= 150:  # ~5 minutes at 2s intervals
            baseline_speeds = [entry["speed"] for entry in self.speed_history[:150]]
            self.baseline_speed = statistics.mean(baseline_speeds)
            logger.info(f"📊 Baseline speed established: {self.baseline_speed:.1f} Mbps")
        
        if self.baseline_speed is None or self.baseline_speed <= 0:
            return
        
        # Check for throttling: consistent low speeds for 10+ minutes
        threshold = self.config.get("throttle_threshold_percent", 30) / 100
        threshold_speed = self.baseline_speed * (1 - threshold)
        
        # Get speeds from last 10 minutes
        ten_minutes_ago = now - timedelta(minutes=10)
        recent_entries = [
            entry for entry in self.speed_history 
            if datetime.fromisoformat(entry["timestamp"].isoformat()) > ten_minutes_ago
        ]
        
        if len(recent_entries) >= 300:  # At least 10 minutes of data
            recent_speeds = [entry["speed"] for entry in recent_entries]
            recent_avg = statistics.mean(recent_speeds)
            
            # Check if 80% of recent speeds are below threshold
            below_threshold_count = sum(1 for speed in recent_speeds if speed < threshold_speed)
            below_threshold_percent = below_threshold_count / len(recent_speeds)
            
            if recent_avg < threshold_speed and below_threshold_percent >= 0.8:
                if not self.throttle_detected:  # Only log once when first detected
                    logger.info(f"🚨 THROTTLING DETECTED! Baseline: {self.baseline_speed:.1f} Mbps, Recent 10min avg: {recent_avg:.1f} Mbps ({below_threshold_percent*100:.1f}% below threshold)")
                self.throttle_detected = True
            else:
                if self.throttle_detected:  # Log when throttling ends
                    logger.info(f"✅ Throttling appears to have ended. Current avg: {recent_avg:.1f} Mbps")
                self.throttle_detected = False

    def save_data(self):
        """Save current statistics to JSON file."""
        now = datetime.now(timezone.utc)
        session_duration = 0
        
        if self.session_start:
            session_duration = int((now - self.session_start).total_seconds())
        
        avg_speed = statistics.mean(self.speed_samples) if self.speed_samples else 0.0
        current_speed = self.speed_samples[-1] if self.speed_samples else 0.0
        
        # Convert speed_history to serializable format
        speed_history_data = []
        for entry in self.speed_history[-100:]:  # Keep last 100 entries
            if isinstance(entry, dict):
                speed_history_data.append({
                    "speed": entry["speed"],
                    "timestamp": entry["timestamp"].isoformat()
                })
            else:
                # Handle old format (just numbers)
                speed_history_data.append({
                    "speed": entry,
                    "timestamp": now.isoformat()
                })
        
        data = {
            "status": "paused" if self.paused else ("running" if self.running else "stopped"),
            "speed_mbps": round(current_speed, 2),
            "total_gb": round(self.total_bytes / (1024**3), 3),
            "session_duration": session_duration,
            "avg_speed": round(avg_speed, 2),
            "peak_speed": round(self.peak_speed, 2),
            "throttle_detected": self.throttle_detected,
            "last_update": now.isoformat(),
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "data_points": self.data_points[-100:],  # Last 100 points for charts
            "errors": self.errors[-10:],  # Last 10 errors
            "baseline_speed": round(self.baseline_speed or 0, 2),
            "data_cap_gb": self.config.get("data_cap_gb", 100),
            "cap_percentage": (self.total_bytes / (1024**3)) / self.config.get("data_cap_gb", 100) * 100,
            "speed_history": speed_history_data,
            "expected_speed_mbps": self.expected_speed,
            "performance_stats": {
                "close_to_expected": round(self.performance_stats["close_to_expected"], 1),
                "far_below_expected": round(self.performance_stats["far_below_expected"], 1),
                "far_above_expected": round(self.performance_stats["far_above_expected"], 1)
            },
            "performance_thresholds": {
                "close_range_low": round(self.expected_speed * 0.8, 1),
                "close_range_high": round(self.expected_speed * 1.2, 1)
            }
        }
        
        try:
            with open(self.data_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def check_pause_resume(self):
        """Check for pause/resume signal files."""
        pause_file = Path("pause.signal")
        resume_file = Path("resume.signal")
        
        if pause_file.exists() and not self.paused:
            self.paused = True
            pause_file.unlink()
            logger.info("Download paused")
        
        if resume_file.exists() and self.paused:
            self.paused = False
            resume_file.unlink()
            logger.info("Download resumed")

    async def run_download_loop(self):
        """Main download loop."""
        mode = "RESUMING" if self.resume_session else "STARTING FRESH"
        logger.info(f"🚀 {mode} download tester...")
        self.running = True
        
        # Only set session start if not already set (for fresh sessions)
        if self.session_start is None:
            self.session_start = datetime.now(timezone.utc)
            logger.info("⏰ Session start time set to now")
        else:
            logger.info(f"⏰ Using existing session start time: {self.session_start}")
        
        logger.info(f"📊 Starting with {self.total_bytes / (1024**3):.3f} GB already downloaded")
        
        # Create HTTP client with connection pooling
        timeout = httpx.Timeout(30.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            url_index = 0
            last_save = time.time()
            download_count = 0
            
            logger.info("🔄 Entering main download loop...")
            
            while self.running:
                # Check for pause/resume signals
                self.check_pause_resume()
                
                if self.paused:
                    if download_count % 30 == 0:  # Log every 30 seconds when paused
                        logger.info("⏸️ Download is paused, waiting...")
                    await asyncio.sleep(1)
                    continue
                
                # Data cap monitoring (no automatic stopping)
                total_gb = self.total_bytes / (1024**3)
                data_cap = self.config.get("data_cap_gb", 100)
                if total_gb >= data_cap:
                    if int(total_gb) % 10 == 0 and int(total_gb) != getattr(self, '_last_logged_gb', 0):
                        # Log every 10GB milestone after exceeding cap
                        logger.info(f"📊 Data usage: {total_gb:.2f} GB (exceeds cap of {data_cap} GB)")
                        self._last_logged_gb = int(total_gb)
                
                # Get next URL in rotation
                urls = self.config["test_urls"]
                url = urls[url_index % len(urls)]
                url_index += 1
                download_count += 1
                
                logger.info(f"🌐 Downloading from: {url[:50]}..." if len(url) > 50 else f"🌐 Downloading from: {url}")
                
                # Download chunk and calculate speed
                bytes_downloaded, time_taken = await self.download_chunk(url, client)
                
                if bytes_downloaded > 0:
                    self.total_bytes += bytes_downloaded
                    speed_mbps = self.calculate_speed(bytes_downloaded, time_taken)
                    self.update_statistics(speed_mbps)
                    
                    logger.info(f"📈 Speed: {speed_mbps:.1f} Mbps | Downloaded: {bytes_downloaded/(1024*1024):.1f} MB | Total: {self.total_bytes / (1024**3):.3f} GB")
                else:
                    logger.warning(f"⚠️ No data downloaded from {url}")
                
                # Save data periodically
                if time.time() - last_save >= self.config.get("update_interval_seconds", 2):
                    self.save_data()
                    last_save = time.time()
                    logger.info(f"💾 Data saved. Session duration: {int((datetime.now(timezone.utc) - self.session_start).total_seconds())}s")
                
                # Short delay to prevent overwhelming the server
                await asyncio.sleep(0.1)
        
        # Final save
        self.save_data()
        logger.info("🏁 Download tester stopped")

    def load_previous_state(self):
        """Load previous session state if resuming."""
        try:
            if Path(self.data_path).exists():
                logger.info(f"📂 Loading previous session from {self.data_path}")
                with open(self.data_path, 'r') as f:
                    previous_data = json.load(f)
                
                # Resume from previous totals
                prev_gb = previous_data.get("total_gb", 0)
                self.total_bytes = int(prev_gb * (1024**3))
                self.peak_speed = previous_data.get("peak_speed", 0.0)
                self.data_points = previous_data.get("data_points", [])[-50:]  # Keep recent points
                self.errors = previous_data.get("errors", [])
                self.baseline_speed = previous_data.get("baseline_speed", None)
                self.throttle_detected = previous_data.get("throttle_detected", False)
                
                # Restore speed history
                speed_history_data = previous_data.get("speed_history", [])
                self.speed_history = []
                for entry in speed_history_data:
                    if isinstance(entry, dict) and "timestamp" in entry:
                        self.speed_history.append({
                            "speed": entry["speed"],
                            "timestamp": datetime.fromisoformat(entry["timestamp"])
                        })
                
                # Restore performance tracking data
                self.expected_speed = previous_data.get("expected_speed_mbps", self.config.get("expected_speed_mbps", 60))
                restored_performance_stats = previous_data.get("performance_stats", {})
                if restored_performance_stats:
                    self.performance_stats = restored_performance_stats
                
                # Rebuild performance samples from data points if available
                self.performance_samples = []
                for point in self.data_points:
                    if isinstance(point, dict) and "performance_category" in point:
                        self.performance_samples.append(point["performance_category"])
                
                # Adjust session start time to account for previous duration
                prev_duration = previous_data.get("session_duration", 0)
                self.session_start = datetime.now(timezone.utc) - timedelta(seconds=prev_duration)
                
                logger.info(f"📈 Successfully resumed session:")
                logger.info(f"   💾 Data: {prev_gb:.3f} GB downloaded")
                logger.info(f"   ⏱️ Duration: {prev_duration//60}m {prev_duration%60}s")
                logger.info(f"   🏃 Peak speed: {self.peak_speed:.1f} Mbps")
                logger.info(f"   🎯 Baseline: {self.baseline_speed or 'Not set'} Mbps")
                logger.info(f"   📊 Data points: {len(self.data_points)}")
                logger.info(f"   📈 Speed history: {len(self.speed_history)} entries")
                logger.info(f"   ⚠️ Errors: {len(self.errors)}")
            else:
                logger.info(f"📂 No previous session file found at {self.data_path}")
                logger.info("🆕 Starting fresh session")
                self.session_start = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"❌ Could not load previous state: {e}")
            logger.info("🆕 Starting fresh session")
            self.session_start = datetime.now(timezone.utc)

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ISP Data Cap Tester - Download Worker")
    parser.add_argument("--resume", action="store_true", help="Resume from previous session")
    args = parser.parse_args()

    tester = DownloadTester(resume_session=args.resume)
    try:
        await tester.run_download_loop()
    except KeyboardInterrupt:
        logger.info("\nShutdown requested...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        tester.running = False
        tester.save_data()

if __name__ == "__main__":
    asyncio.run(main()) 