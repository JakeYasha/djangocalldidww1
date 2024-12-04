import pjsua as pj
import wave
import time
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import threading
import speech_recognition as sr
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

class CallProcessor:
    def __init__(self, base_dir="calls"):
        self.base_dir = base_dir
        self.recognizer = sr.Recognizer()
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

    def create_phone_directory(self, phone_number):
        """Create a directory for the phone number if it doesn't exist"""
        phone_dir = os.path.join(self.base_dir, phone_number)
        if not os.path.exists(phone_dir):
            os.makedirs(phone_dir)
        return phone_dir

    def transcribe_audio(self, audio_file):
        """Transcribe the audio file to text using Google Speech Recognition"""
        try:
            # Convert wav to AudioFile that speech_recognition can use
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
            
            # Perform the transcription
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            print(f"Google Speech Recognition could not understand the audio: {audio_file}")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {str(e)}")
            return None
        except Exception as e:
            print(f"Error transcribing {audio_file}: {str(e)}")
            return None

    def process_recording(self, phone_number, recording_file):
        """Process a single recording file"""
        if not os.path.exists(recording_file):
            return None

        # Create transcript filename
        transcript_file = recording_file.replace('.wav', '.txt')
        
        # Transcribe audio if transcript doesn't exist
        if not os.path.exists(transcript_file):
            print(f"Transcribing {recording_file}...")
            transcript = self.transcribe_audio(recording_file)
            if transcript:
                with open(transcript_file, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                print(f"Transcription saved to {transcript_file}")
                return transcript
        return None

    def monitor_recordings(self, phone_number):
        """Monitor recordings directory for new files"""
        phone_dir = self.create_phone_directory(phone_number)
        recordings_dir = "recordings"  # Original recordings directory
        
        while True:
            try:
                # Check for new recordings
                for file in os.listdir(recordings_dir):
                    if file.endswith('.wav'):
                        src_path = os.path.join(recordings_dir, file)
                        dst_path = os.path.join(phone_dir, file)
                        
                        # Move file to phone directory if not already moved
                        if os.path.exists(src_path) and not os.path.exists(dst_path):
                            os.rename(src_path, dst_path)
                            print(f"Moved recording to {dst_path}")
                            
                            # Process the recording
                            transcript = self.process_recording(phone_number, dst_path)
                            if transcript:
                                print(f"New transcript for {phone_number}: {transcript[:100]}...")
                
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Error in monitoring: {str(e)}")
                time.sleep(5)

# Logging callback
def log_cb(level, msg, length):
    try:
        print(msg.decode('utf-8'))
    except UnicodeDecodeError:
        print("Logging error: Unable to decode message.")

# Call state callback
class CallCallback(pj.CallCallback):
    def __init__(self, call=None):
        super().__init__(call)
        self.recorder_id = None
        self.recording_filename = None

    def on_state(self):
        print(f"Call state: {self.call.info().state_text}")
        if self.call.info().state == pj.CallState.DISCONNECTED:
            if self.recorder_id is not None:
                try:
                    lib.recorder_destroy(self.recorder_id)
                    print(f"Recorder destroyed for: {self.recording_filename}")
                except pj.Error as e:
                    print(f"Error destroying recorder: {str(e)}")
                self.recorder_id = None

    def on_media_state(self):
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            call_slot = self.call.info().conf_slot
            try:
                # Create recordings directory if it doesn't exist
                if not os.path.exists("recordings"):
                    os.makedirs("recordings")
                
                # Generate recording filename
                self.recording_filename = os.path.join(
                    "recordings",
                    f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                )
                
                # Create recorder and connect call slot to recorder slot
                self.recorder_id = lib.create_recorder(self.recording_filename)
                rec_slot = lib.recorder_get_slot(self.recorder_id)
                lib.conf_connect(call_slot, rec_slot)
                print(f"Recording started: {self.recording_filename}")
            except pj.Error as e:
                print(f"Error setting up recorder: {str(e)}")

# Account callback
class AccountCallback(pj.AccountCallback):
    def __init__(self, account=None):
        super().__init__(account)

    def on_reg_state(self):
        print(f"Registration state: {self.account.info().reg_status} ({self.account.info().reg_reason})")

def make_call(lib, acc, number, domain="nyc.us.out.didww.com"):
    try:
        uri = f"sip:{number}@{domain}"
        print(f"Dialing: {uri}")
        call = acc.make_call(uri, cb=CallCallback())
        time.sleep(30)  # Wait for call to finish
        call.hangup()
        print(f"Call ended: {number}")
    except pj.Error as e:
        print(f"Error making call to {number}: {str(e)}")

def process_phone_number(number):
    """Process a single phone number - make call and monitor recordings"""
    processor = CallProcessor()
    
    # Start monitoring thread
    monitor_thread = threading.Thread(
        target=processor.monitor_recordings,
        args=(number,),
        daemon=True
    )
    monitor_thread.start()
    
    # Initialize PJSUA and make the call
    global lib
    lib = pj.Lib()

    try:
        # Configure the library
        media_cfg = pj.MediaConfig()
        media_cfg.no_vad = True
        media_cfg.enable_ice = True
        media_cfg.clock_rate = 16000

        # Configure NAT and UA settings
        ua_cfg = pj.UAConfig()
        ua_cfg.force_lr = True
        ua_cfg.user_agent = "PJSUA v2.14.1 NAT"
        ua_cfg.max_calls = 1
        ua_cfg.nameserver = ["8.8.8.8", "8.8.4.4"]


        lib.init(
            ua_cfg=ua_cfg,
            log_cfg=pj.LogConfig(level=4, callback=log_cb),
            media_cfg=media_cfg
        )

        lib.set_null_snd_dev()
        
        # Create UDP transport
        transport_cfg = pj.TransportConfig()
        transport_cfg.public_addr = os.getenv('LOCAL_IP')
        transport = lib.create_transport(pj.TransportType.UDP, transport_cfg)
        
        lib.start()

        # Configure account
        acc_cfg = pj.AccountConfig()
        acc_cfg.id = f"sip:{os.getenv('SIP_USER')}@{os.getenv('SIP_DOMAIN')}"
        acc_cfg.reg_uri = f"sip:{os.getenv('SIP_DOMAIN')}"
        acc_cfg.auth_cred = [pj.AuthCred(
            os.getenv('SIP_AUTH_REALM'),
            os.getenv('SIP_AUTH_USERNAME'),
            os.getenv('SIP_AUTH_PASSWORD')
        )]
        
        acc_cfg.allow_contact_rewrite = True
        acc_cfg.contact_rewrite_method = 2
        acc_cfg.contact_force_contact = f"sip:{os.getenv('SIP_USER')}@{os.getenv('LOCAL_IP')}"
        acc_cfg.reg_timeout = 300
        acc_cfg.rtp_port = 10000
        acc_cfg.rtp_port_range = 1000
        
        # Create account and make call
        acc = lib.create_account(acc_cfg, cb=AccountCallback())
        time.sleep(3)  # Wait for registration
        
        make_call(lib, acc, number)

    except pj.Error as e:
        print(f"Exception: {str(e)}")
    finally:
        if lib:
            lib.destroy()
            lib = None

def main():
    # Example usage
    number = "18889396675"  # Replace with your target number
    process_phone_number(number)
    
    # Keep main thread alive to allow monitoring to continue
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
