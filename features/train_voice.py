import os
import time
import wave
import numpy as np
import pyaudio
from pathlib import Path
from resemblyzer import VoiceEncoder, preprocess_wav

def record_sample(file_path, duration=4):
    """Ghi âm 1 đoạn giọng mẫu ngắn trong 4 giây"""
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    print(f"\n🔴 [GHI ÂM]: Hãy nói một câu bất kỳ (ví dụ: 'Jarvis khởi động hệ thống')... ({duration}s)")
    frames = []

    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("✅ Đã ghi xong mẫu!")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(file_path, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def create_owner_voice_profile():
    encoder = VoiceEncoder()
    wavs = []
    
    print("==================================================")
    print("🎙️ HỆ THỐNG TẠO DẤU VÂN GIỌNG CHO CHỦ SỞ HỮU (JARVIS)")
    print("==================================================")
    
    # Ghi âm 3 mẫu câu khác nhau
    for i in range(1, 4):
        input(f"\nNhấn ENTER để bắt đầu thu âm MẪU THỨ {i}/3...")
        sample_path = f"sample_owner_{i}.wav"
        record_sample(sample_path)
        
        # Load và preprocess file vừa ghi
        wav = preprocess_wav(Path(sample_path))
        wavs.append(wav)

    print("\n🧠 Đang trích xuất Vector đặc trưng vân giọng của sếp...")
    # Tạo vector đại diện trung bình từ 3 mẫu giọng
    embeds = [encoder.embed_utterance(w) for w in wavs]
    owner_embedding = np.mean(embeds, axis=0)

    # Lưu lại file numpy
    np.save("owner_voice.npy", owner_embedding)
    print("🎉 TẠO HỒ SƠ GIỌNG NÓI THÀNH CÔNG! Đã lưu file 'owner_voice.npy'.")

    # Dọn dẹp các file wav tạm
    for i in range(1, 4):
        if os.path.exists(f"sample_owner_{i}.wav"):
            os.remove(f"sample_owner_{i}.wav")

if __name__ == "__main__":
    create_owner_voice_profile()