#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import base64
import requests
import json
import re
import socket
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from urllib.parse import quote
from pathlib import Path

# Desktop screenshot detection imports (optional)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    DESKTOP_DETECTION_AVAILABLE = True
    print("✅ Desktop auto-detection available")
except ImportError:
    DESKTOP_DETECTION_AVAILABLE = False
    print("⚠️  Desktop auto-detection unavailable. Install with: pip install watchdog")

def get_macos_input(title, prompt, secret=False):
    """Get input via native macOS dialog using osascript"""
    try:
        if secret:
            script = f'''
            display dialog "{prompt}" with title "{title}" ¬
            default answer "" ¬
            with hidden answer ¬
            buttons {{"Cancel", "OK"}} ¬
            default button "OK"
            text returned of result
            '''
        else:
            script = f'''
            display dialog "{prompt}" with title "{title}" ¬
            default answer "" ¬
            buttons {{"Cancel", "OK"}} ¬
            default button "OK"
            text returned of result
            '''
        
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
            
    except Exception as e:
        print(f"macOS dialog failed: {e}")
        return input(f"{prompt}: ").strip()

def show_macos_message(title, message):
    """Show a native macOS message dialog"""
    try:
        script = f'''
        display dialog "{message}" with title "{title}" ¬
        buttons {{"OK"}} ¬
        default button "OK"
        '''
        subprocess.run(['osascript', '-e', script], timeout=30)
    except Exception as e:
        print(f"macOS message failed: {e}")
        print(f"{title}: {message}")

def show_macos_question(title, message):
    """Show a native macOS yes/no dialog"""
    try:
        script = f'''
        display dialog "{message}" with title "{title}" ¬
        buttons {{"No", "Yes"}} ¬
        default button "Yes"
        button returned of result
        '''
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            return result.stdout.strip() == "Yes"
        else:
            return False
    except Exception as e:
        print(f"macOS question failed: {e}")
        return False

class DesktopScreenshotWatcher(FileSystemEventHandler):
    """Handles automatic desktop screenshot detection"""
    
    def __init__(self, processor):
        self.processor = processor
        self.processed_files = set()
        self.last_process_time = {}
        print("🖥️  Desktop auto-detection enabled")
        print(f"📁 Monitoring: {self.get_desktop_path()}")
    
    def get_desktop_path(self):
        """Get the user's Desktop path"""
        return str(Path.home() / "Desktop")
    
    def is_screenshot_file(self, file_path):
        """Check if file is likely a screenshot"""
        file_path = Path(file_path)
        
        # Check file extension
        if file_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
            return False
        
        # Check if it's a recent file (within last 10 seconds)
        try:
            file_age = time.time() - file_path.stat().st_mtime
            if file_age > 10:
                return False
        except:
            return False
        
        # Check filename patterns (macOS screenshot patterns)
        name = file_path.name.lower()
        screenshot_patterns = [
            'screenshot',
            'screen shot', 
            'capture',
            'cleanshot'
        ]
        
        # Check if filename contains screenshot patterns
        if any(pattern in name for pattern in screenshot_patterns):
            return True
        
        # Check if filename follows macOS screenshot pattern
        if name.startswith('screenshot ') and ' at ' in name:
            return True
        
        # Check if it's a CleanShot pattern
        if 'cleanshot' in name:
            return True
        
        return False
    
    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        time.sleep(0.5)  # Wait for file to be fully written
        
        if self.is_screenshot_file(file_path):
            self.process_desktop_screenshot(file_path)
    
    def on_modified(self, event):
        """Handle file modification"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Avoid processing the same file multiple times rapidly
        current_time = time.time()
        if file_path in self.last_process_time:
            if current_time - self.last_process_time[file_path] < 2:
                return
        
        self.last_process_time[file_path] = current_time
        time.sleep(0.5)
        
        if self.is_screenshot_file(file_path) and file_path not in self.processed_files:
            self.process_desktop_screenshot(file_path)
    
    def process_desktop_screenshot(self, file_path):
        """Process desktop screenshot through the main processor"""
        try:
            if file_path in self.processed_files:
                return
            
            self.processed_files.add(file_path)
            
            file_name = Path(file_path).name
            print(f"📸 Auto-detected screenshot: {file_name}")
            
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return
            
            # Check file size before processing (avoid huge screenshots)
            file_size = os.path.getsize(file_path)
            if file_size > 15 * 1024 * 1024:  # 15MB limit for raw files
                print(f"⚠️  Screenshot too large ({file_size/1024/1024:.1f}MB), skipping auto-processing")
                print(f"💡 Use manual processing for large screenshots")
                return
            
            # Read and encode image
            try:
                with open(file_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                print(f"❌ Failed to read image: {e}")
                return
            
            # Check base64 size
            if len(image_data) > 13000000:  # ~13MB base64 limit (safer than 10MB)
                print(f"⚠️  Screenshot too large when encoded ({len(image_data)/1000000:.1f}MB), skipping")
                print(f"💡 Try taking smaller screenshots or use manual processing")
                return
            
            # Process through main processor
            metadata = {
                'source': 'desktop_auto',
                'app': 'macOS Screenshot',
                'filename': file_name,
                'auto_detected': True
            }
            
            result = self.processor.process_screenshot(image_data, metadata)
            
            if result.get('success'):
                print(f"✅ Desktop screenshot processed (ID: {result.get('analysis_id')})")
            else:
                print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error processing desktop screenshot: {e}")

class iOSScreenshotProcessor:
    def __init__(self, api_key, telegram_bot_token=None, telegram_chat_id=None, enable_desktop_detection=False):
        self.api_key = api_key
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.enable_desktop_detection = enable_desktop_detection
        
        # Analysis storage for button callbacks
        self.pending_analyses = {}
        self.callback_lock = threading.Lock()
        self.processing_callbacks = set()
        self.last_update_id = 0
        
        # Request tracking
        self.request_count = 0
        self.last_request_time = None
        
        # Desktop watcher
        self.desktop_observer = None
        self.desktop_watcher = None
        
        # Create HTTP session for API calls
        self.session = requests.Session()
        
        print("✅ iOS Screenshot Processor initialized")
        
        # Start Telegram callback polling if configured
        if self.telegram_bot_token:
            self.start_callback_polling()
        
        # Start desktop detection if enabled
        if self.enable_desktop_detection and DESKTOP_DETECTION_AVAILABLE:
            self.start_desktop_detection()
        elif self.enable_desktop_detection and not DESKTOP_DETECTION_AVAILABLE:
            print("⚠️  Desktop detection requested but watchdog not installed")
    
    def start_desktop_detection(self):
        """Start monitoring desktop for screenshots"""
        try:
            self.desktop_watcher = DesktopScreenshotWatcher(self)
            self.desktop_observer = Observer()
            self.desktop_observer.schedule(
                self.desktop_watcher, 
                self.desktop_watcher.get_desktop_path(), 
                recursive=False
            )
            self.desktop_observer.start()
            print("🔍 Desktop screenshot auto-detection started")
        except Exception as e:
            print(f"❌ Failed to start desktop detection: {e}")
    
    def stop_desktop_detection(self):
        """Stop desktop monitoring"""
        if self.desktop_observer:
            self.desktop_observer.stop()
            self.desktop_observer.join()
            print("🛑 Desktop detection stopped")
    
    def process_screenshot(self, image_base64, metadata=None):
        """Main processing pipeline for iOS screenshots"""
        try:
            self.request_count += 1
            self.last_request_time = datetime.now()
            
            # Determine source type
            source_type = metadata.get('source', 'iOS') if metadata else 'iOS'
            print(f"📱 Processing screenshot #{self.request_count} (source: {source_type})")
            
            # Validate input
            if not image_base64:
                raise ValueError("No image data provided")
            
            # Process image data
            processed_image = self.prepare_image_data(image_base64)
            
            # Generate analysis ID
            analysis_id = str(int(time.time() * 1000))
            
            # Get brief AI summary
            brief_summary = self.get_brief_summary(processed_image, source_type)
            
            # Analyze for content type (webpage, research, etc.)
            content_analysis = self.analyze_for_content_type(processed_image)
            
            # Store analysis data for potential follow-up
            with self.callback_lock:
                self.pending_analyses[analysis_id] = {
                    'image_data': processed_image,
                    'brief_summary': brief_summary,
                    'content_analysis': content_analysis,
                    'metadata': metadata or {},
                    'timestamp': self.last_request_time.isoformat(),
                    'source': source_type
                }
            
            # Format response with context
            response = self.format_response(brief_summary, analysis_id, content_analysis, metadata, source_type)
            
            # Send to Telegram
            if self.telegram_bot_token:
                self.send_telegram_notification(response, analysis_id)
            
            print(f"✅ Screenshot processed successfully (ID: {analysis_id})")
            
            return {
                "success": True,
                "summary": brief_summary,
                "analysis_id": analysis_id,
                "timestamp": self.last_request_time.isoformat(),
                "follow_up_available": True,
                "source": source_type
            }
            
        except Exception as e:
            print(f"❌ Error processing screenshot: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def prepare_image_data(self, image_base64):
        """Prepare base64 image data for AI analysis"""
        try:
            # Remove data URL prefix if present
            if image_base64.startswith('data:image'):
                image_base64 = image_base64.split(',')[1]
            
            # Validate base64
            image_bytes = base64.b64decode(image_base64)
            
            # Increased size limit for desktop screenshots
            if len(image_bytes) > 15 * 1024 * 1024:  # 15MB limit
                raise ValueError("Image too large (max 15MB)")
            
            if len(image_bytes) < 1024:  # 1KB minimum
                raise ValueError("Image too small")
            
            # Determine media type
            if image_bytes.startswith(b'\x89PNG'):
                media_type = "image/png"
            elif image_bytes.startswith(b'\xff\xd8\xff'):
                media_type = "image/jpeg"
            else:
                media_type = "image/png"  # Default assumption
            
            return {
                "base64_data": image_base64,
                "media_type": media_type,
                "size_bytes": len(image_bytes)
            }
            
        except Exception as e:
            raise ValueError(f"Invalid image data: {str(e)}")
    
    def get_brief_summary(self, processed_image, source_type):
        """Get brief AI summary of screenshot"""
        try:
            # Adjust prompt based on source
            if source_type.startswith('desktop'):
                prompt = "Analyze this desktop screenshot briefly. What is shown and what might be the user's intent?"
            else:
                prompt = "Analyze this iPhone screenshot briefly. What is shown and what might be the user's intent?"
            
            response = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 200,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": processed_image["media_type"],
                                    "data": processed_image["base64_data"]
                                }
                            }
                        ]
                    }]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['content'][0]['text']
            else:
                raise Exception(f"Claude API error: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"AI analysis failed: {str(e)}")
    
    def analyze_for_content_type(self, processed_image):
        """Analyze screenshot for content type and context"""
        try:
            analysis_prompt = """Analyze this screenshot and determine:

1. Content type (webpage, app, document, social media, etc.)
2. If webpage: extract any visible URLs or domains
3. If research-related: identify key topics
4. User context: what might they want to do with this?

Respond with:
CONTENT_TYPE: [webpage/app/document/social/game/other]
WEBPAGE_URL: [URL if visible, or "none"]
RESEARCH_TOPICS: [comma-separated topics if research-related]
USER_INTENT: [likely user intent]
FOLLOW_UP: [suggested follow-up actions]"""
            
            response = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 300,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": analysis_prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": processed_image["media_type"],
                                    "data": processed_image["base64_data"]
                                }
                            }
                        ]
                    }]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return self.parse_content_analysis(response.json()['content'][0]['text'])
            else:
                return {"content_type": "unknown", "webpage_url": None}
                
        except Exception as e:
            print(f"Content analysis failed: {str(e)}")
            return {"content_type": "unknown", "webpage_url": None}
    
    def parse_content_analysis(self, analysis_text):
        """Parse structured content analysis response"""
        result = {
            'content_type': 'unknown',
            'webpage_url': None,
            'research_topics': [],
            'user_intent': '',
            'follow_up': ''
        }
        
        try:
            lines = analysis_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('CONTENT_TYPE:'):
                    result['content_type'] = line.split(':', 1)[1].strip()
                elif line.startswith('WEBPAGE_URL:'):
                    url = line.split(':', 1)[1].strip()
                    if url != "none" and url != "unknown":
                        result['webpage_url'] = url
                elif line.startswith('RESEARCH_TOPICS:'):
                    topics = line.split(':', 1)[1].strip()
                    result['research_topics'] = [t.strip() for t in topics.split(',')]
                elif line.startswith('USER_INTENT:'):
                    result['user_intent'] = line.split(':', 1)[1].strip()
                elif line.startswith('FOLLOW_UP:'):
                    result['follow_up'] = line.split(':', 1)[1].strip()
        except Exception as e:
            print(f"Content analysis parsing failed: {str(e)}")
        
        return result
    
    def format_response(self, summary, analysis_id, content_analysis, metadata, source_type):
        """Format response with source-specific context"""
        # Determine emoji and source name
        if source_type.startswith('desktop'):
            source_emoji = "🖥️"
            source_name = "Desktop Screenshot"
        else:
            source_emoji = "📱"
            source_name = "iPhone Screenshot"
        
        response = {
            "source": f"{source_emoji} {source_name}",
            "timestamp": datetime.now().strftime('%H:%M:%S'),
            "summary": summary,
            "analysis_id": analysis_id
        }
        
        # Add metadata context
        if metadata:
            if metadata.get('app'):
                response["app"] = f"📱 {metadata['app']}"
            if metadata.get('location'):
                response["location"] = f"📍 {metadata['location']}"
            if metadata.get('filename'):
                response["filename"] = f"📄 {metadata['filename']}"
        
        # Add content type context
        if content_analysis.get('content_type') != 'unknown':
            response["content_type"] = content_analysis['content_type']
        
        return response
    
    def send_telegram_notification(self, response_data, analysis_id):
        """Send notification to Telegram with screenshot image and action buttons"""
        try:
            # Get the image data for this analysis
            with self.callback_lock:
                if analysis_id not in self.pending_analyses:
                    print("❌ Analysis not found for Telegram notification")
                    return False
                analysis_data = self.pending_analyses[analysis_id]
                image_data = analysis_data['image_data']
            
            # Create action buttons
            buttons = [
                [
                    {
                        "text": "🔬 Research Papers",
                        "callback_data": f"arxiv_research_{analysis_id}"
                    }
                ],
                [
                    {
                        "text": "🧠 Deep Research",
                        "callback_data": f"deep_research_{analysis_id}"
                    }
                ]
            ]
            
            # Add webpage button if detected
            content_analysis = self.pending_analyses.get(analysis_id, {}).get('content_analysis', {})
            if content_analysis.get('webpage_url'):
                buttons.append([
                    {
                        "text": "🌐 Webpage Content",
                        "callback_data": f"full_webpage_{analysis_id}"
                    }
                ])
            
            reply_markup = {"inline_keyboard": buttons}
            
            # Decode base64 image data
            try:
                image_bytes = base64.b64decode(image_data['base64_data'])
                image_size_mb = len(image_bytes) / (1024 * 1024)
                print(f"🔍 Image decoded: {image_size_mb:.1f}MB")
                
                # Check Telegram photo size limit (10MB)
                if len(image_bytes) > 10 * 1024 * 1024:
                    print(f"⚠️  Image too large for Telegram ({image_size_mb:.1f}MB > 10MB)")
                    return self.send_telegram_fallback_message(f"*{response_data['source']}* _{response_data['timestamp']}_\n\n{response_data['summary']}", reply_markup)
                    
            except Exception as e:
                print(f"❌ Failed to decode image: {e}")
                return False
            
            # SHORT caption for the photo (under 1024 characters)
            short_caption = f"*{response_data['source']}* _{response_data['timestamp']}_"
            
            # Add basic metadata if present
            if 'filename' in response_data:
                short_caption += f"\n{response_data['filename']}"
            
            short_caption += f"\n_ID: {analysis_id}_"
            
            # Send photo with SHORT caption and buttons
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
            
            files = {
                'photo': ('screenshot.png', image_bytes, image_data['media_type'])
            }
            
            data = {
                'chat_id': self.telegram_chat_id,
                'caption': short_caption,
                'parse_mode': 'Markdown',
                'reply_markup': json.dumps(reply_markup)
            }
            
            print(f"📤 Sending {image_size_mb:.1f}MB photo with short caption...")
            
            # Send the photo
            response = self.session.post(url, files=files, data=data, timeout=180)
            
            if response.status_code == 200:
                print("📤 ✅ Screenshot sent successfully!")
                
                # Now send the FULL analysis as a separate text message
                full_message = f"**AI Analysis:**\n\n{response_data['summary']}"
                
                # Add any additional metadata
                if 'app' in response_data:
                    full_message += f"\n\n{response_data['app']}"
                if 'location' in response_data:
                    full_message += f"\n{response_data['location']}"
                
                # Send the full analysis
                self.send_telegram_message(full_message)
                
                return True
            else:
                print(f"📤 ❌ Telegram photo error: {response.status_code}")
                print(f"📤 ❌ Error response: {response.text}")
                
                # Fallback: send as text message only
                print("📤 ⚠️  Falling back to text-only message...")
                full_caption = f"*{response_data['source']}* _{response_data['timestamp']}_\n\n{response_data['summary']}"
                return self.send_telegram_fallback_message(full_caption, reply_markup)
                
        except Exception as e:
            print(f"📤 ❌ Failed to send Telegram photo: {str(e)}")
            return False

    def send_telegram_fallback_message(self, message, reply_markup):
        """Fallback method to send text-only message if photo fails"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": f"📷 Screenshot processed\n\n{message}",
                "parse_mode": "Markdown",
                "reply_markup": json.dumps(reply_markup),
                "disable_web_page_preview": True
            }
            
            response = self.session.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                print("📤 Fallback text notification sent to Telegram")
                return True
            else:
                print(f"📤 Fallback message also failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"📤 Fallback message failed: {str(e)}")
            return False

    def start_callback_polling(self):
        """Start polling for Telegram callback queries"""
        def poll():
            while True:
                try:
                    self.check_for_callbacks()
                    time.sleep(2)
                except Exception as e:
                    print(f"Callback polling error: {e}")
                    time.sleep(5)
        
        polling_thread = threading.Thread(target=poll, daemon=True)
        polling_thread.start()
        print("🔄 Telegram callback polling started")

    def check_for_callbacks(self):
        """Check for and handle Telegram callback queries"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 1}
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return
            
            data = response.json()
            if not data.get('ok') or not data.get('result'):
                return
            
            for update in data['result']:
                self.last_update_id = update['update_id']
                
                if 'callback_query' in update:
                    callback_query = update['callback_query']
                    callback_data = callback_query['data']
                    callback_id = callback_query['id']
                    
                    self.handle_callback(callback_data, callback_id)
                    
        except Exception as e:
            pass  # Silently handle polling errors

    def handle_callback(self, callback_data, callback_id):
        """Handle Telegram button press callbacks"""
        try:
            # Answer callback to remove loading state
            self.session.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/answerCallbackQuery",
                data={"callback_query_id": callback_id}
            )
            
            # Check if already processing
            with self.callback_lock:
                if callback_data in self.processing_callbacks:
                    return
                self.processing_callbacks.add(callback_data)
            
            try:
                # Extract analysis ID and action
                if callback_data.startswith("arxiv_research_"):
                    analysis_id = callback_data.replace("arxiv_research_", "")
                    self.send_arxiv_research_summary(analysis_id)
                elif callback_data.startswith("deep_research_"):
                    analysis_id = callback_data.replace("deep_research_", "")
                    self.send_deep_research_analysis(analysis_id)
                elif callback_data.startswith("full_webpage_"):
                    analysis_id = callback_data.replace("full_webpage_", "")
                    self.send_webpage_analysis(analysis_id)
            finally:
                with self.callback_lock:
                    self.processing_callbacks.discard(callback_data)
                
        except Exception as e:
            print(f"Callback handling error: {e}")

    def send_telegram_message(self, message):
        """Send text message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = self.session.post(url, data=data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Failed to send message: {str(e)}")
            return False
    
    def send_arxiv_research_summary(self, analysis_id):
        """Send arXiv research analysis"""
        try:
            with self.callback_lock:
                if analysis_id not in self.pending_analyses:
                    return
                analysis_data = self.pending_analyses[analysis_id]
            
            # Extract research keywords
            keywords = self.extract_research_keywords(analysis_data['image_data'])
            
            if not keywords or not keywords.get('is_research'):
                message = "*arXiv Research Analysis*\n\nThis screenshot doesn't appear to contain research-related content."
            else:
                papers = self.search_arxiv_papers(keywords['keywords'])
                
                if not papers:
                    message = f"*arXiv Research Analysis*\n\nNo related papers found for keywords: {', '.join(keywords['keywords'])}"
                else:
                    message = f"*arXiv Research Analysis*\n\n"
                    message += f"**Field**: {keywords['field']}\n"
                    message += f"**Keywords**: {', '.join(keywords['keywords'][:5])}\n\n"
                    message += f"**Related Papers ({len(papers)} found):**\n\n"
                    
                    for i, paper in enumerate(papers[:3], 1):
                        authors_str = ', '.join(paper['authors'][:2])
                        if len(paper['authors']) > 2:
                            authors_str += " et al."
                        
                        title = paper['title'][:80] + "..." if len(paper['title']) > 80 else paper['title']
                        
                        message += f"**{i}. {title}**\n"
                        message += f"Authors: {authors_str}\n"
                        message += f"Published: {paper['published']}\n"
                        message += f"Link: {paper['id']}\n\n"
            
            self.send_telegram_message(message)
            
        except Exception as e:
            self.send_telegram_message(f"Research analysis failed: {str(e)}")
    
    def extract_research_keywords(self, image_data):
        """Extract research keywords from image"""
        try:
            keyword_prompt = """Analyze this screenshot and extract potential research keywords or academic topics.

Respond with:
KEYWORDS: [comma-separated list of 3-7 relevant research keywords]
IS_RESEARCH: [yes/no - whether this appears to be research-related content]
FIELD: [primary research field if identifiable]"""
            
            response = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 200,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": keyword_prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_data["media_type"],
                                    "data": image_data["base64_data"]
                                }
                            }
                        ]
                    }]
                }
            )
            
            if response.status_code == 200:
                analysis = response.json()['content'][0]['text']
                return self.parse_keyword_analysis(analysis)
            else:
                return None
                
        except Exception as e:
            return None
    
    def parse_keyword_analysis(self, analysis_text):
        """Parse keyword analysis response"""
        result = {'is_research': False, 'keywords': [], 'field': 'unknown'}
        
        try:
            lines = analysis_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('KEYWORDS:'):
                    keywords_str = line.split(':', 1)[1].strip()
                    result['keywords'] = [k.strip() for k in keywords_str.split(',')]
                elif line.startswith('IS_RESEARCH:'):
                    result['is_research'] = 'yes' in line.lower()
                elif line.startswith('FIELD:'):
                    result['field'] = line.split(':', 1)[1].strip()
        except Exception as e:
            pass
        
        return result
    
    def search_arxiv_papers(self, keywords, max_results=5):
        """Search arXiv papers using keywords"""
        try:
            search_terms = ' AND '.join(keywords[:3])
            query = quote(search_terms)
            
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            papers = []
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                paper = {}
                paper['id'] = entry.find('{http://www.w3.org/2005/Atom}id').text
                paper['title'] = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                
                authors = []
                for author in entry.findall('{http://www.w3.org/2005/Atom}author'):
                    name = author.find('{http://www.w3.org/2005/Atom}name').text
                    authors.append(name)
                paper['authors'] = authors
                
                published = entry.find('{http://www.w3.org/2005/Atom}published').text
                paper['published'] = published[:10]
                
                papers.append(paper)
            
            return papers
            
        except Exception as e:
            return []
    
    def send_deep_research_analysis(self, analysis_id):
        """Send comprehensive research analysis"""
        self.send_telegram_message("🔬 *Deep Research Analysis*\n\nStarting comprehensive analysis... This may take 1-2 minutes.")
        
        try:
            with self.callback_lock:
                if analysis_id not in self.pending_analyses:
                    return
                analysis_data = self.pending_analyses[analysis_id]
            
            # Generate comprehensive analysis
            research_summary = self.generate_comprehensive_analysis(analysis_data['image_data'])
            
            message = f"🔬 *Deep Research Analysis Complete*\n\n{research_summary}"
            self.send_telegram_message(message)
            
        except Exception as e:
            self.send_telegram_message(f"Deep research analysis failed: {str(e)}")
    
    def generate_comprehensive_analysis(self, image_data):
        """Generate comprehensive analysis of the screenshot"""
        try:
            prompt = """Provide a comprehensive analysis of this screenshot covering:

1. **Content Overview** - What is shown and its context
2. **Key Insights** - Important information or patterns
3. **Practical Applications** - How this information could be used
4. **Follow-up Suggestions** - Recommended next steps

Provide a detailed but well-organized analysis."""
            
            response = self.session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 800,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_data["media_type"],
                                    "data": image_data["base64_data"]
                                }
                            }
                        ]
                    }]
                }
            )
            
            if response.status_code == 200:
                return response.json()['content'][0]['text']
            else:
                return "Comprehensive analysis generation failed"
                
        except Exception as e:
            return f"Error generating analysis: {str(e)}"
    
    def send_webpage_analysis(self, analysis_id):
        """Send webpage content analysis"""
        try:
            with self.callback_lock:
                if analysis_id not in self.pending_analyses:
                    return
                analysis_data = self.pending_analyses[analysis_id]
            
            content_analysis = analysis_data.get('content_analysis', {})
            webpage_url = content_analysis.get('webpage_url')
            
            if not webpage_url:
                message = "*Webpage Analysis*\n\nNo webpage URL detected in this screenshot."
            else:
                # Fetch and analyze webpage content
                webpage_content = self.fetch_webpage_content(webpage_url)
                if webpage_content.get('success'):
                    message = f"*Webpage Analysis*\n\n**URL**: {webpage_url}\n**Title**: {webpage_content['title']}\n\n{webpage_content['summary']}"
                else:
                    message = f"*Webpage Analysis*\n\nFailed to fetch content from: {webpage_url}"
            
            self.send_telegram_message(message)
            
        except Exception as e:
            self.send_telegram_message(f"Webpage analysis failed: {str(e)}")
    
    def fetch_webpage_content(self, url):
        """Fetch and summarize webpage content"""
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Simple content extraction (you could use BeautifulSoup for better parsing)
            title = "Webpage Content"
            if '<title>' in response.text:
                title_start = response.text.find('<title>') + 7
                title_end = response.text.find('</title>')
                if title_end > title_start:
                    title = response.text[title_start:title_end].strip()
            
            # Generate summary of webpage
            summary = f"Successfully fetched webpage content from {url}"
            
            return {
                'title': title,
                'summary': summary,
                'url': url,
                'success': True
            }
            
        except Exception as e:
            return {
                'title': None,
                'summary': None,
                'url': url,
                'success': False,
                'error': str(e)
            }
    
    def send_telegram_message(self, message):
        """Send text message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = self.session.post(url, data=data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Failed to send message: {str(e)}")
            return False
    
    def cleanup_old_analyses(self):
        """Clean up old analysis data"""
        with self.callback_lock:
            if len(self.pending_analyses) > 20:
                sorted_ids = sorted(self.pending_analyses.keys(), key=int)
                to_remove = sorted_ids[:len(sorted_ids)//2]
                for analysis_id in to_remove:
                    del self.pending_analyses[analysis_id]
                print(f"🧹 Cleaned up {len(to_remove)} old analyses")

# Flask App Setup
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit
app.config['JSON_AS_ASCII'] = False

processor = None

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

@app.route('/screenshot', methods=['POST'])
def handle_screenshot():
    """Main endpoint for iOS screenshot processing"""
    try:
        # DEBUG: Let's see exactly what iPhone is sending
        print(f"🔍 Content-Type: {request.content_type}")
        print(f"🔍 Raw data length: {len(request.get_data())}")
        
        # BYPASS Flask's JSON parsing - handle raw data manually
        raw_data = request.get_data()
        if not raw_data:
            return jsonify({"error": "No data provided"}), 400
        
        try:
            # Parse JSON manually from raw bytes
            import json
            data = json.loads(raw_data.decode('utf-8'))
            print(f"✅ Successfully parsed JSON with {len(data)} keys")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
        except Exception as e:
            print(f"❌ Data parsing error: {e}")
            return jsonify({"error": f"Data parsing failed: {str(e)}"}), 400
        
        # Rest of your existing code...
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        image_base64 = data.get('image')
        metadata = data.get('metadata', {})
        
        if not image_base64:
            return jsonify({"error": "No image data provided"}), 400
        
        # Process screenshot
        result = processor.process_screenshot(image_base64, metadata)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "server": "iOS Screenshot AI Server",
        "timestamp": datetime.now().isoformat(),
        "requests_processed": processor.request_count if processor else 0,
        "desktop_detection": processor.enable_desktop_detection if processor else False
    })

@app.route('/status', methods=['GET'])
def status():
    """Server status endpoint"""
    if processor:
        return jsonify({
            "server": "iOS Screenshot AI Server",
            "status": "running",
            "local_ip": get_local_ip(),
            "port": 5001,
            "total_requests": processor.request_count,
            "last_request": processor.last_request_time.isoformat() if processor.last_request_time else None,
            "active_analyses": len(processor.pending_analyses),
            "telegram_configured": bool(processor.telegram_bot_token),
            "desktop_detection_enabled": processor.enable_desktop_detection,
            "desktop_detection_available": DESKTOP_DETECTION_AVAILABLE
        })
    else:
        return jsonify({"status": "initializing"})

@app.route('/toggle-desktop', methods=['POST'])
def toggle_desktop_detection():
    """Toggle desktop screenshot detection on/off"""
    if not processor:
        return jsonify({"error": "Processor not initialized"}), 500
    
    try:
        enable = request.json.get('enable', False)
        
        if enable and not DESKTOP_DETECTION_AVAILABLE:
            return jsonify({
                "success": False,
                "error": "Desktop detection requires 'pip install watchdog'"
            }), 400
        
        if enable and not processor.enable_desktop_detection:
            processor.enable_desktop_detection = True
            processor.start_desktop_detection()
            message = "Desktop auto-detection enabled"
        elif not enable and processor.enable_desktop_detection:
            processor.enable_desktop_detection = False
            processor.stop_desktop_detection()
            message = "Desktop auto-detection disabled"
        else:
            message = f"Desktop auto-detection already {'enabled' if enable else 'disabled'}"
        
        return jsonify({
            "success": True,
            "message": message,
            "desktop_detection_enabled": processor.enable_desktop_detection
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def load_env_file():
    """Load environment variables from .env file"""
    env_file = '.env'
    if os.path.exists(env_file):
        print(f"📁 Loading environment from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def main():
    # Fix working directory for PyInstaller GUI launches
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            bundle_dir = sys._MEIPASS
            os.chdir(bundle_dir)
            print(f"🔧 Changed working directory to: {bundle_dir}")
        else:
            bundle_dir = os.path.dirname(sys.executable)
            os.chdir(bundle_dir)
            print(f"🔧 Changed working directory to: {bundle_dir}")
    
    global processor
    
    print("📱 iOS Screenshot AI Server")
    print("=" * 40)
    
    # Load configuration
    load_env_file()
    
    API_KEY = os.getenv('ANTHROPIC_API_KEY')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    ENABLE_DESKTOP = os.getenv('ENABLE_DESKTOP_DETECTION', 'false').lower() == 'true'
    
    # Get API key with native macOS dialog
    if not API_KEY:
        show_macos_message("iOS Screenshot AI Setup", 
                          "Welcome to iOS Screenshot AI!\\n\\nYou need to provide your Anthropic API key to get started.\\n\\nGet your key from: https://console.anthropic.com/")
        
        API_KEY = get_macos_input("iOS Screenshot AI - API Key", 
                                 "Enter your Anthropic API key:", 
                                 secret=True)
        
        if not API_KEY:
            show_macos_message("Error", "Anthropic API key is required!")
            return
    else:
        print("✅ Anthropic API key loaded from .env")
    
    # Get Telegram credentials (optional) with native dialogs
    if not TELEGRAM_BOT_TOKEN:
        wants_telegram = show_macos_question("iOS Screenshot AI - Telegram Setup", 
                                           "Would you like to configure Telegram notifications?\\n\\n(Optional - you can skip this)")
        if wants_telegram:
            TELEGRAM_BOT_TOKEN = get_macos_input("Telegram Setup", 
                                               "Enter your Telegram Bot Token\\n(Get from @BotFather):")
    
    if TELEGRAM_BOT_TOKEN and not TELEGRAM_CHAT_ID:
        TELEGRAM_CHAT_ID = get_macos_input("Telegram Setup", 
                                         "Enter your Telegram Chat ID\\n(Get from @userinfobot):")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        print("✅ Telegram configured")
        show_macos_message("Setup Complete", "✅ Telegram notifications configured!")
    else:
        print("⚠️  Telegram not configured - summaries will only be returned to iOS")
    
    # Ask about desktop detection
    if not ENABLE_DESKTOP and DESKTOP_DETECTION_AVAILABLE:
        wants_desktop = show_macos_question("Desktop Auto-Detection", 
                                          "Enable automatic desktop screenshot processing?\\n\\nThis will automatically analyze any screenshots you take on your Mac.")
        ENABLE_DESKTOP = wants_desktop
    
    if ENABLE_DESKTOP and DESKTOP_DETECTION_AVAILABLE:
        print("✅ Desktop auto-detection will be enabled")
    elif ENABLE_DESKTOP and not DESKTOP_DETECTION_AVAILABLE:
        print("⚠️  Desktop detection requested but requires: pip install watchdog")
        ENABLE_DESKTOP = False
    else:
        print("⚠️  Desktop auto-detection disabled")
    
    # Initialize processor
    processor = iOSScreenshotProcessor(
        API_KEY, 
        TELEGRAM_BOT_TOKEN, 
        TELEGRAM_CHAT_ID,
        enable_desktop_detection=ENABLE_DESKTOP
    )
    
    # Get local IP
    local_ip = get_local_ip()
    
    print("=" * 40)
    print(f"🖥️  Computer IP: {local_ip}")
    print(f"🌐 Server URL: http://{local_ip}:5001")
    print(f"📱 iOS Endpoint: http://{local_ip}:5001/screenshot")
    print(f"🔍 Health Check: http://{local_ip}:5001/health")
    if ENABLE_DESKTOP:
        print(f"🖥️  Desktop Detection: ENABLED")
    print("=" * 40)
    
    # Show setup complete message with native dialog
    features_text = "📱 iOS Screenshots + 🖥️ Desktop Auto-Detection" if ENABLE_DESKTOP else "📱 iOS Screenshots"
    setup_message = f"🎉 iOS Screenshot AI is now running!\\n\\n🖥️ Computer IP: {local_ip}\\n📱 iOS Endpoint: http://{local_ip}:5001/screenshot\\n\\n{features_text}\\n\\nSetup your iPhone:\\n1. Create a new Shortcut\\n2. Use 'Get Contents of URL' action\\n3. POST to: http://{local_ip}:5001/screenshot\\n\\nThe server will keep running until you quit this app."
    
    show_macos_message("Setup Complete", setup_message)
    
    print("✅ Both iPhone and computer must be on the same WiFi")
    print("📱 Configure iOS Shortcut to POST to the endpoint above")
    if ENABLE_DESKTOP:
        print("🖥️  Take any screenshot - it will be auto-processed!")
    print("🔄 Server starting...")
    print("=" * 40)
    
    try:
        # Start Flask server
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        if processor and processor.desktop_observer:
            processor.stop_desktop_detection()
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        show_macos_message("Error", f"Server error: {str(e)}")
        if processor and processor.desktop_observer:
            processor.stop_desktop_detection()

if __name__ == "__main__":
    main()
