import pjsua as pj
import wave
import time
import sys
import os
import logging
import traceback
from datetime import datetime
import signal

import socket
import struct
import random

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sip_caller.log')
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные
lib = None
call = None
acc = None
quit_flag = False
wav_player = None
call_slot = None

def signal_handler(signum, frame):
    global quit_flag
    logger.info("Signal received, stopping...")
    quit_flag = True

# Logging callback
def log_cb(level, msg, length):
    try:
        message = msg.decode('utf-8', errors='replace')
        logger.info(f"PJSIP: {message}")
    except Exception as e:
        logger.error(f"Error in log callback: {str(e)}")

# Call state callback
class CallCallback(pj.CallCallback):
    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)
        self.recorder_id = None
        self.recording_filename = None
        self.call_state = None
        self.rtp_stats = {'tx_packets': 0, 'rx_packets': 0}
        self.last_log_time = time.time()
        self.media_start_time = None  # Добавляем это
        self.dtmf_sent = False


    def send_dtmf_rtp(self, digit, duration=160, volume=10):
        """
        Send DTMF using raw UDP socket with RFC 2833 format
        
        Args:
            digit: DTMF character (0-9,*,#,A-D)
            duration: Duration in timestamp units (default 160 = 20ms @ 8kHz)
            volume: Volume level 0-63 (default 10)
        """
        try:
            # Get call info
            call_info = self.call.info()
            
            # Log call state for debugging
            logger.info("\n=== Call Info for DTMF ===")
            logger.info(f"State: {call_info.state}")
            logger.info(f"State text: {call_info.state_text}")
            
            # DTMF event mapping
            dtmf_events = {
                '0': 0, '1': 1, '2': 2, '3': 3, '4': 4,
                '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
                '*': 10, '#': 11, 'A': 12, 'B': 13, 'C': 14, 'D': 15
            }
            
            event = dtmf_events.get(str(digit).upper())
            if event is None:
                raise ValueError(f"Invalid DTMF digit: {digit}")

            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Get remote RTP address from SDP (hardcoded from the log for testing)
            remote_ip = "46.19.209.17"
            remote_port = 23680
            
            # RTP header fields
            version = 2
            padding = 0
            extension = 0
            csrc_count = 0
            marker = 1
            payload_type = 101  # RFC 2833 events
            sequence = random.randint(0, 65535)
            timestamp = random.randint(0, 2**32 - 1)
            ssrc = random.randint(0, 2**32 - 1)
            
            # Pack RTP header (12 bytes)
            # Format: !BBHII (! = network byte order)
            # Byte 1: Version(2), Padding(1), Extension(1), CSRC count(4)
            # Byte 2: Marker(1), Payload type(7)
            # Bytes 3-4: Sequence number
            # Bytes 5-8: Timestamp
            # Bytes 9-12: SSRC
            rtp_header = struct.pack('!BBHII',
                (version << 6) | (padding << 5) | (extension << 4) | csrc_count,
                (marker << 7) | payload_type,
                sequence,
                timestamp,
                ssrc)
                
            # Create DTMF event payload
            dtmf_payload = bytes([
                event,                    # Event ID
                0x80 | (volume & 0x3F),  # End=1, Reserved=0, Volume=volume
                (duration >> 8) & 0xFF,   # Duration high byte
                duration & 0xFF           # Duration low byte
            ])
            
            # Combine RTP header and DTMF payload
            rtp_packet = rtp_header + dtmf_payload
            
            # Send packet
            sock.sendto(rtp_packet, (remote_ip, remote_port))
            
            # Send end packet after 20ms
            time.sleep(0.02)
            
            # Update sequence and timestamp
            sequence = (sequence + 1) & 0xFFFF
            timestamp = (timestamp + 160) & 0xFFFFFFFF
            
            # Create end packet
            rtp_header = struct.pack('!BBHII',
                (version << 6) | (padding << 5) | (extension << 4) | csrc_count,
                (marker << 7) | payload_type,
                sequence,
                timestamp,
                ssrc)
                
            dtmf_payload = bytes([
                event,                    # Event ID
                0xC0 | (volume & 0x3F),  # End=1, Reserved=1, Volume=volume
                (duration >> 8) & 0xFF,   # Duration high byte
                duration & 0xFF           # Duration low byte
            ])
            
            rtp_packet = rtp_header + dtmf_payload
            sock.sendto(rtp_packet, (remote_ip, remote_port))
            
            # Close socket
            sock.close()
            
            logger.info(f"\n\nDTMF {digit} sent via raw UDP to {remote_ip}:{remote_port}\n\n")
            
        except Exception as e:
            logger.error(f"Error sending DTMF via RTP: {str(e)}")
            if 'sock' in locals():
                sock.close()

    def on_state(self):
        global call
        try:
            self.call_state = self.call.info().state
            logger.info(f"Call state changed to: {self.call.info().state_text}")
            
            # Логируем RTP статистику при отключении
            if self.call.info().state == pj.CallState.DISCONNECTED:
                self._log_final_rtp_stats()
                if self.recorder_id is not None:
                    try:
                        lib.recorder_destroy(self.recorder_id)
                        logger.info(f"Recorder successfully destroyed for: {self.recording_filename}")
                    except pj.Error as e:
                        logger.error(f"Error destroying recorder: {str(e)}")
                    finally:
                        self.recorder_id = None
                call = None
        except Exception as e:
            logger.error(f"Error in on_state: {str(e)}\n{traceback.format_exc()}")

    def on_media_state(self):
        global wav_player, call_slot
        try:
            if self.call.info().media_state == pj.MediaState.ACTIVE:
                
                logger.info("\n\n\n\nSET TIME MEDIA START\n\n\n\n\n")
                self.media_start_time = time.time()
                call_slot = self.call.info().conf_slot
                logger.info("Media state is active, setting up recording...")
                
                # Логируем информацию о медиа-транспорте
                self._log_media_transport_info()
                
                # Create recordings directory structure
                try:
                    os.makedirs("recordings", exist_ok=True)
                    
                    # Get destination number from call info
                    dest_number = self.call.info().remote_uri.split("sip:")[1].split("@")[0]
                    number_dir = os.path.join("recordings", dest_number)
                    os.makedirs(number_dir, exist_ok=True)
                    
                    # Generate recording filename
                    self.recording_filename = os.path.join(
                        number_dir,
                        f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    )
                except OSError as e:
                    logger.error(f"Failed to create directory structure: {str(e)}")
                    return

                try:
                    # Create and set up recorder
                    self.recorder_id = lib.create_recorder(self.recording_filename)
                    rec_slot = lib.recorder_get_slot(self.recorder_id)
                    lib.conf_connect(call_slot, rec_slot)
                    logger.info(f"Recording started: {self.recording_filename}")

                    # Create and connect silent wav player
                    wav_player = lib.create_player(
                        "/dev/zero",
                        loop=True,
                        ptime=20,
                        bits_per_sample=16,
                        channel_count=1
                    )
                    wav_slot = lib.player_get_slot(wav_player)
                    lib.conf_connect(wav_slot, call_slot)
                    logger.info("Silent wav player connected successfully")
                    
                except pj.Error as e:
                    logger.error(f"Error in media setup: {str(e)}")
                    if self.recorder_id is not None:
                        try:
                            lib.recorder_destroy(self.recorder_id)
                        except:
                            pass
                        self.recorder_id = None
                        
        except Exception as e:
            logger.error(f"Error in on_media_state: {str(e)}\n{traceback.format_exc()}")

    def _log_media_transport_info(self):
        """Логирование информации о медиа-транспорте"""
        try:
            med_info = self.call.info().media[0]
            rtp_tp = med_info.rtp_tx_pt
            local_rtp = med_info.rtp_addr
            remote_rtp = med_info.peer_addr
            
            logger.info("\n=== RTP TRANSPORT INFORMATION ===")
            logger.info(f"Local RTP Address: {local_rtp}")
            logger.info(f"Remote RTP Address: {remote_rtp}")
            logger.info(f"RTP Payload Type: {rtp_tp}")
            logger.info("================================\n")
        except Exception as e:
            logger.error(f"Error logging media transport info: {str(e)}")

    def _log_final_rtp_stats(self):
        """Логирование финальной RTP статистики"""
        try:
            med_info = self.call.info().media[0]
            stats = med_info.rtcp.stat
            
            logger.info("\n=== FINAL RTP STATISTICS ===")
            logger.info(f"Transmitted packets: {stats.tx.pkt}")
            logger.info(f"Received packets: {stats.rx.pkt}")
            logger.info(f"Lost packets: {stats.rx.loss}")
            logger.info(f"Jitter: {stats.rx.jitter_usec/1000.0}ms")
            logger.info("===========================\n")
        except Exception as e:
            logger.error(f"Error logging final RTP stats: {str(e)}")

    def on_stream_created(self, stream):
        """Обработчик создания медиа-потока"""
        try:
            logger.info("\n=== NEW RTP STREAM CREATED ===")
            logger.info(f"Stream type: {stream.type}")
            logger.info(f"Remote address: {stream.info().sock_info.raddr}")
            logger.info(f"Local address: {stream.info().sock_info.laddr}")
            logger.info("============================\n")
        except Exception as e:
            logger.error(f"Error in stream creation handler: {str(e)}")

    def on_stream_destroyed(self, stream):
        """Обработчик уничтожения медиа-потока"""
        try:
            logger.info(f"\nRTP Stream destroyed: {stream.type}")
        except Exception as e:
            logger.error(f"Error in stream destruction handler: {str(e)}")

# Account callback
class AccountCallback(pj.AccountCallback):
    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)
        self.account = account
        self.registration_complete = False

    def on_reg_state(self):
        self.registration_complete = (self.account.info().reg_status >= 200 and self.account.info().reg_status < 300)
        logger.info(f"Registration state: {self.account.info().reg_status} ({self.account.info().reg_reason})")
        if self.registration_complete:
            logger.info("Registration completed")

def wait_for_registration(acc_cb, timeout=5):
    try:
        start_time = time.time()
        while not acc_cb.registration_complete:
            lib.handle_events(10)
            if time.time() - start_time > timeout:
                logger.warning("Registration timeout reached")
                return False
        return True
    except Exception as e:
        logger.error(f"Error in wait_for_registration: {str(e)}")
        return False

def main():
    global lib, acc, call, quit_flag, wav_player
    
    try:
        # Set up signal handling
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Initializing PJSUA library...")
        
        # Create library instance
        lib = pj.Lib()

        # Configure the library
        ua_cfg = pj.UAConfig()
        ua_cfg.max_calls = 1
        ua_cfg.user_agent = "PJSUA Simple Caller"
        ua_cfg.nameserver = ["8.8.8.8", "8.8.4.4"]

        media_cfg = pj.MediaConfig()
        media_cfg.no_vad = True
        media_cfg.enable_ice = False
        media_cfg.clock_rate = 8000
        media_cfg.snd_clock_rate = 8000
        media_cfg.audio_frame_ptime = 20
        media_cfg.channel_count = 1

        # Initialize library with Null Sound Device
        lib.init(
            ua_cfg=ua_cfg,
            log_cfg=pj.LogConfig(level=4, callback=log_cb),
            media_cfg=media_cfg
        )

        # Set null sound device
        lib.set_null_snd_dev()

        # Create UDP transport
        transport = lib.create_transport(pj.TransportType.UDP)
        logger.info(f"Transport created on port {transport.info().port}")

        # Start library
        lib.start()

        # Configure SIP account
        acc_cfg = pj.AccountConfig()
        acc_cfg.id = f"sip:{os.getenv('SIP_USER')}@{os.getenv('SIP_DOMAIN')}"
        acc_cfg.reg_uri = f"sip:{os.getenv('SIP_DOMAIN')}"
        acc_cfg.auth_cred = [pj.AuthCred(
            os.getenv('SIP_AUTH_REALM'),
            os.getenv('SIP_AUTH_USERNAME'),
            os.getenv('SIP_AUTH_PASSWORD')
        )]

        # Create account and set callback
        acc_cb = AccountCallback()
        acc = lib.create_account(acc_cfg, cb=acc_cb)
        acc_cb.account = acc

        # Wait for registration
        logger.info("Waiting for registration...")
        if not wait_for_registration(acc_cb):
            logger.error("Registration timeout")
            return 1

        # Make call
        number = "18008677183"
        logger.info(f"\nCalling {number}...")
        
        call_cb = CallCallback()
        call = acc.make_call(f"sip:{number}@{os.getenv('SIP_DOMAIN')}", cb=call_cb)

        # Main event loop
        call_duration = 0
        while not quit_flag and call_duration < 30:
            lib.handle_events(100)
            if call_cb.call_state == pj.CallState.DISCONNECTED:
                break

            # Проверяем условия для отправки DTMF
            if (call_cb.media_start_time is not None and 
                not call_cb.dtmf_sent and 
                time.time() - call_cb.media_start_time >= 10):
                try:
                    call_cb.send_dtmf_rtp('2')
                    call_cb.dtmf_sent = True
                    logger.info("\n\n\n\nDTMF '2' sent after 10 seconds\n\n\n\n")
                except Exception as e:
                    logger.error(f"Failed to send DTMF: {str(e)}")
                    

            time.sleep(0.1)
            call_duration += 0.1

        # Cleanup
        if call:
            logger.info("Hanging up the call...")
            call.hangup()
            
        # Wait for hangup to complete
        time.sleep(1)
        while not quit_flag:
            lib.handle_events(100)
            if not call or call_cb.call_state == pj.CallState.DISCONNECTED:
                break
            time.sleep(0.1)

    except pj.Error as e:
        logger.error(f"Exception: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Exception: {str(e)}")
        return 1
    finally:
        # Cleanup
        try:
            if wav_player:
                try:
                    wav_player.stop()
                    lib.player_destroy(wav_player)
                except:
                    pass

            if call:
                try:
                    call.hangup()
                except:
                    pass

            if acc:
                try:
                    acc.delete()
                except:
                    pass

            if lib:
                try:
                    lib.destroy()
                except:
                    pass
        except:
            pass

    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
Инструкция по запуску тестового файла:

1. Убедитесь, что все необходимые переменные окружения установлены:
   - SIP_USER
   - SIP_DOMAIN
   - SIP_AUTH_REALM
   - SIP_AUTH_USERNAME
   - SIP_AUTH_PASSWORD

2. Запустите скрипт:
   python simple_caller.py

3. Логи будут записываться в два места:
   - Консоль (стандартный вывод)
   - Файл sip_caller.log в той же директории

4. В логах вы увидите:
   - Информацию о RTP транспорте (локальные и удаленные адреса)
   - Статистику по RTP пакетам (отправленные, полученные, потерянные)
   - Информацию о создании и уничтожении RTP потоков
   - Джиттер и другие метрики качества связи

5. Для просмотра логов в реальном времени можно использовать:
   tail -f sip_caller.log

Примечание: файл лога sip_caller.log добавлен в .gitignore и не будет отслеживаться в git.
"""
