from pydub import AudioSegment
from pydub.playback import play
import time

def test_sound():
    print("Starting sound test...")
    try:
        # Load the audio file
        sound = AudioSegment.from_mp3("ben1.mp3")
        # Take first 10 seconds
        ten_seconds = sound[:10000]
        # Play the sound
        print("Playing test sound for 10 seconds...")
        play(ten_seconds)
        print("Sound test completed successfully!")
        return True
    except Exception as e:
        print(f"Error during sound test: {str(e)}")
        return False

if __name__ == "__main__":
    test_sound()
