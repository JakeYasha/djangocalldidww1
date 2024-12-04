import pjsua as pj
import wave
import time
import sys
import os
from datetime import datetime
from dotenv import load_dotenv
from phone_numbers.models import PhoneNumber

# Load environment variables from .env file
load_dotenv()

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
        self.phone_number = None

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
                # Create base recordings directory if it doesn't exist
                if not os.path.exists("recordings"):
                    os.makedirs("recordings")
                
                # Create directory for this phone number
                phone_dir = os.path.join("recordings", self.phone_number)
                if not os.path.exists(phone_dir):
                    os.makedirs(phone_dir)
                
                # Generate recording filename
                self.recording_filename = os.path.join(
                    phone_dir,
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

# Function to check if a call should be made
def should_make_call(number):
    try:
        phone_record = PhoneNumber.objects.get(number=number)
        if phone_record.call_attempts >= 15:
            # Check if there are any recordings for this number
            if not phone_record.call_records.exists():
                phone_record.status = 'failed'
                phone_record.save()
                print(f"Error: Number {number} has {phone_record.call_attempts} attempts and no recordings. Status set to error.")
                return False
        return True
    except PhoneNumber.DoesNotExist:
        print(f"Phone number {number} not found in database.")
        return False

# Make a call
def make_call(lib, acc, number, domain="nyc.us.out.didww.com"):
    if not should_make_call(number):
        print(f"Skipping call to {number} due to excessive attempts.")
        return None

    try:

        uri = f"sip:{number}@{domain}"
        print(f"Dialing: {uri}")
        callback = CallCallback()
        callback.phone_number = number  # Store phone number in callback
        call = acc.make_call(uri, cb=callback)
        time.sleep(30)  # Wait for call to finish
        call.hangup()
        print(f"Call ended: {number}")
        
        # Return the recording filename if available
        if hasattr(callback, 'recording_filename'):
            return callback.recording_filename
        return None
        
    except (pj.Error, PhoneNumber.DoesNotExist) as e:
        print(f"Error making call to {number}: {str(e)}")
        return None

# Main function
def main():
    global lib

    # Initialize the library
    lib = pj.Lib()
    
    try:
        # Configure the library
        media_cfg = pj.MediaConfig()
        media_cfg.no_vad = True
        media_cfg.enable_ice = True  # Enable ICE for NAT traversal
        media_cfg.clock_rate = 16000
        
        # Configure NAT and UA settings
        ua_cfg = pj.UAConfig()
        ua_cfg.force_lr = True
        ua_cfg.user_agent = "PJSUA v2.14.1 NAT"
        ua_cfg.max_calls = 1
        ua_cfg.nameserver = ["8.8.8.8", "8.8.4.4"]

        # Initialize library
        lib.init(
            ua_cfg=ua_cfg,
            log_cfg=pj.LogConfig(level=4, callback=log_cb),
            media_cfg=media_cfg
        )

        # Use NULL sound device
        lib.set_null_snd_dev()
        print("Using NULL audio device")

        # Create UDP transport with STUN
        transport_cfg = pj.TransportConfig()
        transport_cfg.public_addr = os.getenv('LOCAL_IP')
        transport = lib.create_transport(pj.TransportType.UDP, transport_cfg)
        print(f"Transport created with public address {transport_cfg.public_addr}")
        print(f"Local binding: {transport.info().host}:{transport.info().port}")

        

        # Configure SIP account with enhanced NAT settings
        acc_cfg = pj.AccountConfig()
        acc_cfg.id = f"sip:{os.getenv('SIP_USER')}@{os.getenv('SIP_DOMAIN')}"
        acc_cfg.reg_uri = f"sip:{os.getenv('SIP_DOMAIN')}"
        acc_cfg.auth_cred = [pj.AuthCred(
            os.getenv('SIP_AUTH_REALM'),
            os.getenv('SIP_AUTH_USERNAME'),
            os.getenv('SIP_AUTH_PASSWORD')
        )]
        
        # Enhanced NAT and media settings
        acc_cfg.allow_contact_rewrite = True
        acc_cfg.contact_rewrite_method = 2
        acc_cfg.contact_force_contact = f"sip:{os.getenv('SIP_USER')}@{os.getenv('LOCAL_IP')}"
        acc_cfg.reg_timeout = 300
        
        # Set RTP port range
        acc_cfg.rtp_port = 10000
        acc_cfg.rtp_port_range = 1000  # Use ports 10000-11000 for RTP
        
        # Create account
        acc = lib.create_account(acc_cfg, cb=AccountCallback())
        
        # Wait for registration to complete
        print("Waiting for registration...")
        time.sleep(3)

        # Phone numbers to call
        numbers = ["18889396675", "18555294494", "12064707000"]

        # Make calls sequentially
        for number in numbers:
            print(f"\nCalling {number}...")
            make_call(lib, acc, number)
            time.sleep(2)  # Small delay between calls

    except pj.Error as e:
        print(f"Exception: {str(e)}")
        sys.exit(1)

    finally:
        # Ensure library is properly destroyed
        if lib:
            print("Destroying library...")
            lib.destroy()
            lib = None

if __name__ == "__main__":
    main()
