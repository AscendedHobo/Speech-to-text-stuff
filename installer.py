import whisper

models = ["tiny", "base", "small", "medium", "large"]

for m in models:
    print(f"Downloading model: {m}")
    whisper.load_model(m)
