import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from app.services.cosyvoice_tts import synthesize_speech, cosyvoice_model, init_cosyvoice_tts_service
from app.services.voice_clone import voice_cloner
import app.utils.tts_metrics as tts_metrics
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, UploadFile
from app.services.voice_service import (
    get_voice_samples, 
    compare_voice_samples,
    process_voice_sample
)
from app.services.cosyvoice_tts import (
    synthesize_speech, 
    get_tts_task_status, 
    get_tts_task_result
)
from app.services.course_service import (
    upload_courseware,
    extract_text,
    generate_voiced_courseware,
    get_task_status as get_course_task_status,
    get_task_result as get_course_task_result
)
from app.services.replace_service import (
    upload_media,
    transcribe_media,
    replace_voice,
    get_task_status as get_replace_task_status,
    get_subtitles,
    get_task_result as get_replace_task_result
)
from app.core.config import settings

# Metrics tracking service
class MetricsService:
    def __init__(self):
        self.metrics_file = os.path.join(settings.UPLOAD_DIR, "app_metrics.json")
        self.metrics = {
            "voice_samples": 0,
            "tts_tasks": 0,
            "courseware_tasks": 0,
            "replace_tasks": 0,
            "total_processing_time": 0,
            "average_quality_score": 0.0,
            "total_audio_duration": 0,
            "usage_history": []
        }
        self.load_metrics()
    
    def load_metrics(self):
        """Load metrics from file if it exists"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    self.metrics = data
            except Exception as e:
                print(f"Failed to load metrics: {e}")
    
    async def save_metrics(self):
        """Save metrics to file"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, default=str)
    
    async def record_voice_sample(self, quality_score: float = 0.0):
        """Record a new voice sample"""
        self.metrics["voice_samples"] += 1
        
        # Update average quality score
        if quality_score > 0:
            current_total = self.metrics["average_quality_score"] * (self.metrics["voice_samples"] - 1)
            new_average = (current_total + quality_score) / self.metrics["voice_samples"]
            self.metrics["average_quality_score"] = new_average
        
        # Add to usage history
        self.metrics["usage_history"].append({
            "type": "voice_sample",
            "timestamp": datetime.now().isoformat(),
            "quality_score": quality_score
        })
        
        await self.save_metrics()
    
    async def record_tts_task(self, duration: float = 0.0, processing_time: float = 0.0):
        """Record a new TTS task"""
        self.metrics["tts_tasks"] += 1
        self.metrics["total_audio_duration"] += duration
        self.metrics["total_processing_time"] += processing_time
        
        # Add to usage history
        self.metrics["usage_history"].append({
            "type": "tts",
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "processing_time": processing_time
        })
        
        await self.save_metrics()
    
    async def record_courseware_task(self, slides_count: int = 0, processing_time: float = 0.0):
        """Record a new courseware task"""
        self.metrics["courseware_tasks"] += 1
        self.metrics["total_processing_time"] += processing_time
        
        # Add to usage history
        self.metrics["usage_history"].append({
            "type": "courseware",
            "timestamp": datetime.now().isoformat(),
            "slides_count": slides_count,
            "processing_time": processing_time
        })
        
        await self.save_metrics()
    
    async def record_replace_task(self, duration: float = 0.0, processing_time: float = 0.0):
        """Record a new replacement task"""
        self.metrics["replace_tasks"] += 1
        self.metrics["total_audio_duration"] += duration
        self.metrics["total_processing_time"] += processing_time
        
        # Add to usage history
        self.metrics["usage_history"].append({
            "type": "replace",
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "processing_time": processing_time
        })
        
        await self.save_metrics()
    
    async def get_metrics(self) -> Dict:
        """Get current metrics summary"""
        # Calculate some derived metrics
        if self.metrics["tts_tasks"] + self.metrics["courseware_tasks"] + self.metrics["replace_tasks"] > 0:
            total_tasks = self.metrics["tts_tasks"] + self.metrics["courseware_tasks"] + self.metrics["replace_tasks"]
            avg_processing_time = self.metrics["total_processing_time"] / total_tasks
        else:
            avg_processing_time = 0
            
        # Format metrics for display
        return {
            "voice_samples_count": self.metrics["voice_samples"],
            "tts_tasks_count": self.metrics["tts_tasks"],
            "courseware_tasks_count": self.metrics["courseware_tasks"],
            "replace_tasks_count": self.metrics["replace_tasks"],
            "total_processed_audio": f"{self.metrics['total_audio_duration']:.2f} seconds",
            "average_processing_time": f"{avg_processing_time:.2f} seconds",
            "average_quality_score": f"{self.metrics['average_quality_score']:.2f}",
            "recent_activity": self.metrics["usage_history"][-5:] if self.metrics["usage_history"] else []
        }

# Create a metrics service instance
metrics_service = MetricsService()

# Application integration utilities

async def process_voice_sample_with_metrics(sample):
    """Process a voice sample and record metrics"""
    # Process the sample
    await process_voice_sample(sample)
    
    # Get the processed sample to check quality score
    samples = await get_voice_samples(0, 1, None, sample.id)
    if samples and len(samples) > 0:
        quality_score = samples[0].quality_score or 0.0
        # Record metrics
        await metrics_service.record_voice_sample(quality_score)

async def synthesize_speech_with_metrics(bg_tasks, text, voice_id, params):
    """Synthesize speech and record metrics"""
    start_time = datetime.now()
    
    # Submit the TTS task
    task_id = await synthesize_speech(bg_tasks, text, voice_id, params)
    
    # Check task status asynchronously to record metrics when done
    bg_tasks.add_task(wait_for_tts_completion, task_id, start_time)
    
    return task_id

async def wait_for_tts_completion(task_id, start_time):
    """Wait for TTS task to complete and record metrics"""
    # Poll for completion
    while True:
        status = await get_tts_task_status(task_id)
        if status and status.status in ["completed", "failed"]:
            break
        await asyncio.sleep(0.5)
    
    # Calculate processing time
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    # Record metrics if task completed successfully
    if status and status.status == "completed":
        duration = status.duration or 0.0
        await metrics_service.record_tts_task(duration, processing_time)

async def generate_voiced_courseware_with_metrics(bg_tasks, file_id, voice_id, speed):
    """Generate voiced courseware and record metrics"""
    start_time = datetime.now()
    
    # Submit the courseware task
    task_id = await generate_voiced_courseware(bg_tasks, file_id, voice_id, speed)
    
    # Check task status asynchronously to record metrics when done
    bg_tasks.add_task(wait_for_courseware_completion, task_id, start_time)
    
    return task_id

async def wait_for_courseware_completion(task_id, start_time):
    """Wait for courseware task to complete and record metrics"""
    # Poll for completion
    while True:
        status = await get_course_task_status(task_id)
        if status and status.status in ["completed", "failed"]:
            break
        await asyncio.sleep(1.0)
    
    # Calculate processing time
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    # Record metrics if task completed successfully
    if status and status.status == "completed":
        slides_count = status.total_slides or 0
        await metrics_service.record_courseware_task(slides_count, processing_time)

async def replace_voice_with_metrics(bg_tasks, transcription_task_id, voice_id, speed):
    """Replace voice in media and record metrics"""
    start_time = datetime.now()
    
    # Submit the replace task
    task_id = await replace_voice(bg_tasks, transcription_task_id, voice_id, speed)
    
    # Check task status asynchronously to record metrics when done
    bg_tasks.add_task(wait_for_replace_completion, task_id, start_time)
    
    return task_id

async def wait_for_replace_completion(task_id, start_time):
    """Wait for replace task to complete and record metrics"""
    # Poll for completion
    while True:
        status = await get_replace_task_status(task_id)
        if status and status.status in ["completed", "failed"]:
            break
        await asyncio.sleep(1.0)
    
    # Calculate processing time
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    # Record metrics if task completed successfully
    if status and status.status == "completed":
        # Try to get duration from original media
# Try to get duration from original media
        duration = 0.0
        if status.original_duration:
            duration = float(status.original_duration)
        await metrics_service.record_replace_task(duration, processing_time)

# Initialize app metrics
async def init_app_metrics():
    """Initialize application metrics"""
    # Create required directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "metrics"), exist_ok=True)
    
    # Load initial metrics
    await metrics_service.get_metrics()

# Create a startup task to initialize metrics
async def startup_event():
    await init_app_metrics()

# Register startup event
def register_startup(app: FastAPI):
    app.add_event_handler("startup", startup_event)
    app.add_event_handler("startup", init_cosyvoice_tts_service)
# Get the metrics
async def get_app_metrics():
    return await metrics_service.get_metrics()