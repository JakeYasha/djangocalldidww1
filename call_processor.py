import os
import time
from datetime import datetime
import threading
import queue
import whisper
from transformers import pipeline
import sip_caller

class CallProcessor:
    def __init__(self):
        self.base_dir = "recordings"
        self.audio_queue = queue.Queue()
        self.transcription_model = whisper.load_model("base")
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        
    def create_phone_directory(self, phone_number):
        """Create a directory for the phone number if it doesn't exist"""
        dir_path = os.path.join(self.base_dir, phone_number)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return dir_path

    def process_call(self, phone_number):
        """Main function to handle the call process"""
        # Create directory for phone number
        phone_dir = self.create_phone_directory(phone_number)
        
        # Start monitoring thread for new recordings
        monitor_thread = threading.Thread(
            target=self._monitor_recordings,
            args=(phone_dir,)
        )
        monitor_thread.start()
        
        # Make the call
        try:
            sip_caller.main([phone_number])
        except Exception as e:
            print(f"Error making call to {phone_number}: {str(e)}")
        
        # Wait for recording processing to complete
        monitor_thread.join(timeout=300)  # 5 minutes timeout
        
    def _monitor_recordings(self, phone_dir):
        """Monitor directory for new recordings and process them"""
        initial_files = set(os.listdir(phone_dir))
        check_count = 0
        
        while check_count < 60:  # Check for 5 minutes (5 sec intervals)
            time.sleep(5)
            current_files = set(os.listdir(phone_dir))
            new_files = current_files - initial_files
            
            for file in new_files:
                if file.endswith('.wav'):
                    file_path = os.path.join(phone_dir, file)
                    self._process_audio_file(file_path)
                    
            check_count += 1
            initial_files = current_files

    def _process_audio_file(self, audio_path):
        """Process a single audio file - transcribe and summarize"""
        try:
            # Transcribe audio
            print(f"Transcribing {audio_path}...")
            result = self.transcription_model.transcribe(audio_path)
            transcript = result["text"]
            
            # Save transcript
            transcript_path = audio_path.replace('.wav', '_transcript.txt')
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            # Generate summary if transcript is long enough
            if len(transcript.split()) > 30:  # Only summarize if there's enough text
                summary = self.summarizer(transcript, max_length=130, min_length=30)[0]['summary_text']
                summary_path = audio_path.replace('.wav', '_summary.txt')
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
            
            print(f"Processed {audio_path}")
            
        except Exception as e:
            print(f"Error processing {audio_path}: {str(e)}")

def process_phone_number(phone_number):
    """Main entry point to process a phone number"""
    processor = CallProcessor()
    processor.process_call(phone_number)

if __name__ == "__main__":
    # Example usage
    phone_number = "18889396675"  # Example phone number
    process_phone_number(phone_number)
